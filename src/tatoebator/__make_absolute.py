import os
import re


from tatoebator.constants import ADDON_NAME


# Get the root directory of the script execution
def get_project_root():
    return os.path.abspath(os.getcwd())


# Find all local Python modules
def find_local_modules(root):
    local_modules = []
    for dirpath, _, filenames in os.walk(root):
        rel_dirpath = os.path.relpath(dirpath, root)
        if rel_dirpath.startswith("lib"): continue
        if rel_dirpath.startswith("backup"): continue
        if rel_dirpath.startswith("old tests"): continue
        for filename in filenames:
            if not filename.endswith(".py"): continue
            if filename.startswith("__make_absolute"): continue
            rel_path = os.path.join(rel_dirpath, filename)
            module_name = rel_path[:-3].replace(os.path.sep, ".")
            if module_name[0] == ".": module_name = module_name[2:]
            local_modules.append(module_name)
    return local_modules

def make_imports_relative(module, local_modules):
    module_depth = module.count(".")
    file_path = os.path.join(root, module.replace(".", os.path.sep) + ".py")
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_lines = []
    for line in lines:
        new_line = None
        match = re.match(r"(\s*)(from|import) ([\.\w]+)", line)
        if match:
            indentation, keyword, module = match.groups()
            if module.startswith(ADDON_NAME):
                rel_module = module.replace(ADDON_NAME,"."*module_depth)
                new_line = line.replace(module, rel_module)
                print(line+new_line)
        if new_line is None:
            new_line = line
        new_lines.append(new_line)
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def make_imports_absolute(module, local_modules):
    module_depth = module.count(".")
    file_path = os.path.join(root, module.replace(".", os.path.sep) + ".py")
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_lines = []
    for line in lines:
        new_line = None
        match = re.match(r"(\s*)(from|import) ([\.\w]+)", line)
        if match:
            indentation, keyword, module = match.groups()
            if module.startswith("."):
                abs_module = re.sub(r'^\.+',ADDON_NAME+".",module)
                new_line = line.replace(module, abs_module)
                print(line+new_line)
        if new_line is None:
            new_line = line
        new_lines.append(new_line)
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)



if __name__ == "__main__":
    root = get_project_root()
    local_modules = find_local_modules(root)

    for module in local_modules:
        make_imports_relative(module, local_modules)
        #make_imports_absolute(module, local_modules)
