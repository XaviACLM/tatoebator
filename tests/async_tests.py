import asyncio

from tatoebator.util import sync_gen_from_async_gen


async def main(how_many: int):
    second_eval_tasks_queue = set()
    finished_queue = asyncio.Queue(maxsize=1)

    async def second_step(i):
        await asyncio.sleep(0.5)
        if i%4==0:
            return
        await finished_queue.put(i)

    async def first_step():
        for i in range(100):
            if i%3==0:
                continue
            while len(second_eval_tasks_queue)>=10:
                await asyncio.sleep(0.1)
            print("creating task for",i)
            task = asyncio.create_task(second_step(i))
            second_eval_tasks_queue.add(task)
            task.add_done_callback(second_eval_tasks_queue.discard)
            await asyncio.sleep(0)
        await asyncio.gather(*second_eval_tasks_queue)
        await finished_queue.put(None)

    emitter_task = asyncio.create_task(first_step())
    count = 0
    while True:
        item = await finished_queue.get()
        if item is None:
            return
        print(item)
        count += 1
        if count==how_many:
            break

    emitter_task.cancel()
    for task in second_eval_tasks_queue:
        task.cancel()



async def main(how_many: int):
    BATCH_SIZE = 3
    MAX_SIMUL_JOBS = 10
    MAX_SIMUL_BATCHES = MAX_SIMUL_JOBS//BATCH_SIZE
    second_eval_queue = asyncio.Queue(maxsize=BATCH_SIZE)
    second_eval_batched_tasks = set()
    finished_queue = asyncio.Queue(maxsize=1)


    async def second_step_batched(i_list):
        print("batch processing",i_list)
        await asyncio.sleep(0.5)
        i_list = list(filter(lambda x:x%4!=0,i_list))
        #might retry here if fails
        for i in i_list:
            await finished_queue.put(i)

    async def second_step_batch_creator():
        while True:
            if second_eval_queue.qsize()<BATCH_SIZE:
                await asyncio.sleep(0)
            else:
                batch = [await second_eval_queue.get() for _ in range(BATCH_SIZE)]
                while len(second_eval_batched_tasks)>=MAX_SIMUL_BATCHES:
                    await asyncio.sleep(0)
                task = asyncio.create_task(second_step_batched(batch))
                second_eval_batched_tasks.add(task)
                task.add_done_callback(second_eval_batched_tasks.discard)


    async def first_step():
        for i in range(12):
            if i%3==0:
                continue
            await second_eval_queue.put(i)
            await asyncio.sleep(0)
        await asyncio.gather(*second_eval_batched_tasks)
        await finished_queue.put(None)

    emitter_task = asyncio.create_task(first_step())
    batcher_task = asyncio.create_task(second_step_batch_creator())
    count = 0
    while True:
        item = await finished_queue.get()
        if item is None:
            break
        print(item)
        count += 1
        if count==how_many:
            return
    last_batch_size = second_eval_queue.qsize()
    last_batch = [await second_eval_queue.get() for _ in range(last_batch_size)]
    last_batch_task = asyncio.create_task(second_step_batched(last_batch))
    for _ in range(last_batch_size):
        print(await finished_queue.get())
    return

@sync_gen_from_async_gen
async def yielder(how_many: int):
    BATCH_SIZE = 3
    MAX_SIMUL_JOBS = 10
    MAX_SIMUL_BATCHES = MAX_SIMUL_JOBS//BATCH_SIZE
    second_eval_queue = asyncio.Queue(maxsize=BATCH_SIZE)
    second_eval_batched_tasks = set()
    finished_queue = asyncio.Queue(maxsize=1)


    async def second_step_batched(i_list):
        print("batch processing",i_list)
        await asyncio.sleep(0.5)
        i_list = list(filter(lambda x:x%4!=0,i_list))
        #might retry here if fails
        for i in i_list:
            await finished_queue.put(i)

    async def second_step_batch_creator():
        while True:
            if second_eval_queue.qsize()<BATCH_SIZE:
                await asyncio.sleep(0)
            else:
                batch = [await second_eval_queue.get() for _ in range(BATCH_SIZE)]
                while len(second_eval_batched_tasks)>=MAX_SIMUL_BATCHES:
                    await asyncio.sleep(0)
                task = asyncio.create_task(second_step_batched(batch))
                second_eval_batched_tasks.add(task)
                task.add_done_callback(second_eval_batched_tasks.discard)


    async def first_step():
        for i in range(12):
            if i%3==0:
                continue
            await second_eval_queue.put(i)
            await asyncio.sleep(0)
        await asyncio.gather(*second_eval_batched_tasks)
        await finished_queue.put(None)

    emitter_task = asyncio.create_task(first_step())
    batcher_task = asyncio.create_task(second_step_batch_creator())
    count = 0
    while True:
        item = await finished_queue.get()
        if item is None:
            break
        yield item
        count += 1
        if count==how_many:
            return
    last_batch_size = second_eval_queue.qsize()
    last_batch = [await second_eval_queue.get() for _ in range(last_batch_size)]
    last_batch_task = asyncio.create_task(second_step_batched(last_batch))
    for _ in range(last_batch_size):
        yield await finished_queue.get()
    return

for i in yielder(20):
    print(i)

#asyncio.run(main(20))