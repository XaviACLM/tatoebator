import itertools
import os
from fractions import Fraction

import networkx as nx
import numpy as np

from tatoebator.constants import PATH_TO_OTHER_DATA

max_pol = 6
polygons = []
for n_vertices in range(2, max_pol + 1):
    for phase in (0, Fraction(1, 2 * n_vertices)):
        polygons.append([Fraction(i, n_vertices) + phase for i in range(n_vertices)])


# late addition - popping some polygons with few outgoing neighbors drastically decreases minimum error
polygons.pop(8)
polygons.pop(4)
polygons.pop(0)


reduced_polygons = [(len(p), p[0].numerator == 1) for p in polygons]


def overlap(p1, p2):
    return set(p1) & set(p2)


n_polygons = len(polygons)
adjacent = np.zeros((n_polygons, n_polygons))
for (i, p1), (j, p2) in itertools.product(enumerate(polygons), repeat=2):
    adjacent[i, j] = not overlap(p1, p2)
G = nx.from_numpy_array(adjacent, nodelist=reduced_polygons)

# alright, time to figure out if the stationary is any good
transition = np.maximum(0, adjacent)
transition /= np.sum(transition, axis=0, keepdims=True)


def compute_error(transition: np.array):
    eig_val, eig_vec = np.linalg.eig(transition)
    i = np.argmin(np.abs(eig_val - 1))
    eig_val, eig_vec = eig_val[i], eig_vec[:, i].real
    if not np.abs(eig_val - 1) < 1e-3:
        print(np.abs(eig_val - 1))
        raise Exception()
    eig_vec /= np.sum(eig_vec)
    error = np.sum(np.abs(eig_vec - 1 / eig_vec.size))
    # error = np.sum((np.abs(eig_vec-1/eig_vec.size))**2)
    return error


print(compute_error(transition))


# 0.3 - that's not great. Let's do some crappy constrained finite-differences gradient descent


def crappy_gradient_descent():
    constrained_to_zero = lambda i, j: adjacent[i, j]

    def enforce_distribution_validity(transition: np.array):
        transition = np.maximum(0, transition)
        transition /= np.sum(transition, axis=0, keepdims=True)
        return transition

    def optimization_step(transition: np.array, learning_rate=0.01, delta=1e-5):
        n = transition.shape[0]
        grad = np.zeros((n, n))
        for i, j in itertools.product(range(n), repeat=2):
            if constrained_to_zero(i, j):
                continue

            transition[i, j] += delta
            err_upper = compute_error(transition)
            transition[i, j] -= 2 * delta
            err_lower = compute_error(transition)
            transition[i, j] += delta

            grad[i, j] = (err_upper - err_lower) / 2 * delta
        transition -= learning_rate * grad
        transition = enforce_distribution_validity(transition)
        return transition

    transition = enforce_distribution_validity(adjacent.copy())
    for _ in range(1000):
        print(compute_error(transition))
        transition = optimization_step(transition, learning_rate=0.01, delta=1e-5)


# that didn't work. what about the scipy optimizer? isn't that for multilinear stuff? let's ask cgpt

def crappy_mlin_optimization():
    from scipy.optimize import minimize

    # Flatten only nonzero entries
    indices = np.where(adjacent)
    x0 = transition[indices]
    n = transition.shape[0]

    def objective(x):
        temp_matrix = np.zeros_like(transition)
        temp_matrix[indices] = x
        temp_matrix /= temp_matrix.sum(axis=0, keepdims=True)  # Normalize columns
        return compute_error(temp_matrix)

    # Column sum constraints
    constraints = []
    for j in range(n):
        def col_constraint(x, j=j):
            temp_matrix = np.zeros_like(transition)
            temp_matrix[indices] = x
            return np.sum(temp_matrix[:, j]) - 1

        constraints.append({'type': 'eq', 'fun': col_constraint})

    # Run optimizer
    result = minimize(objective, x0, constraints=constraints, method='SLSQP')
    optimized_transition = np.zeros_like(transition)
    optimized_transition[indices] = result.x
    optimized_transition /= optimized_transition.sum(axis=0, keepdims=True)  # Normalize

    print(f"Final Error: {compute_error(optimized_transition)}")


# that didn't work either. jeez, man. What if we try to do it by hand, i guess?
# we want things to be uniform at exit. but they already are. uhh, assume final stationary on outgoing nodes is
# proportional to probability on outgoing edges - this might be sort of true if we do updates simultaneously. so
# we have probabilities of exit nodes in the stationary, sp1,...,spm, and our own outgoing probabilities on the edges,
# ep1,...,epn, and we gotta modify epi st. it continues being a valid probability distribution AND ep{i}*sp{i} is as
# close to uniform as possible.
# but that's easy: just take the inverses of spi and normalize that (restricted to outgoing neighbors)

def just_do_it_by_hand():
    def compute_stationary(transition: np.array):
        eig_val, eig_vec = np.linalg.eig(transition)
        i = np.argmin(np.abs(eig_val - 1))
        eig_val, eig_vec = eig_val[i], eig_vec[:, i].real
        if not np.abs(eig_val - 1) < 1e-3:
            print(np.abs(eig_val - 1))
            raise Exception()
        eig_vec /= np.sum(eig_vec)
        return eig_vec

    def compute_error(stationary):
        error = np.sum(np.abs(stationary - 1 / stationary.size))
        # error = np.sum((np.abs(eig_vec-1/eig_vec.size))**2)
        return error

    def compute_restricted_stationary(stationary):
        return adjacent * np.expand_dims(stationary, 1)

    def update_transition(transition, learning_rate=1):
        stationary = compute_stationary(transition)
        restricted_stationary = compute_restricted_stationary(stationary)
        new_transition = np.where(adjacent, 1 / restricted_stationary, 0)
        new_transition /= np.sum(new_transition, axis=0, keepdims=True)
        return learning_rate * new_transition + (1 - learning_rate) * transition

    transition = np.maximum(0, adjacent)
    transition /= np.sum(transition, axis=0, keepdims=True)

    np.set_printoptions(formatter={'float': lambda x: "-----" if np.abs(x) < 1e-10 else "{0:0.3f}".format(x)},
                        linewidth=np.inf)
    for _ in range(1000):
        # print(compute_error(compute_stationary(transition)))
        # print(transition)
        transition = update_transition(transition, learning_rate=0.01)

    stationary = compute_stationary(transition)
    error = compute_error(stationary)
    print(error)
    print(stationary)
    return transition


transition = just_do_it_by_hand()
# 0.24 isn't great, but the stationary doesn't look too bad:
# [0.040 0.085 0.063 0.063 0.027 0.095 0.063 0.063 0.040 0.085 0.063 0.063 0.019 0.105 0.063 0.063]
# we mostly just wanted to avoid having anything going too high
# in retrospect it is clear that the problem is fundamentally impossible: Imagine a graph w vertices ABC,
# A->B->A, A->C->A, stationary at A must always be 0.5, some obs reveals lowest error possible is 0.33

# aamof if you do the same trick with more middle vertices the suprema of the infimum error is 0.5. I wonder if this
# is the highest it can go?
# it seems reasonable: obviously paths from one vertex to itself can be nulled if this vertex has too high stationary,
# so random walks always take at least 2 steps to return to a vertex, so stationary for any one vertex cannot be higher
# than 1/2. obviously this isn't even a proof sketch but it does seem like other constructions cannot do better (worse)
# than this middle dominating vertex idea...

# also changing max vertex to 7 because who needs that many vertices. Numbers above change, but surprisingly little

print(transition)
print(reduced_polygons)

data_filepath = os.path.join(PATH_TO_OTHER_DATA, "polygon_transitions.txt")
with open(data_filepath, "w") as f:
    f.write("# Data about the transition matrix for polygons on the loading spinner. Tab-separated values.\n"
            "# First is number of polygons, then one line for each polygon: amt vertices, and whether it is askew\n"
            "# (this meaning that the first vertex is rotated out by half a polygon's section worth of radians).\n"
            "# After this the transition matrix, where i-row j-col is the probability of going from the i-th to the\n"
            "# j-th polygon.\n")
    f.write(f'{n_polygons}\n')
    for n_vertices, askew in reduced_polygons:
        f.write(f'{n_vertices}\t{askew}\n')
    for i in range(n_polygons):
        f.write('\t'.join(map(str,transition[:,i])))
        f.write('\n')