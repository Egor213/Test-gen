import pytest

# from src.manager.project import ProjectManager


# @pytest.fixture
# def project_root(tmp_path):
#     root = tmp_path / "proj"
#     root.mkdir()
#     return root


# @pytest.fixture
# def project_entrypoint(project_root):
#     file = project_root / "main.py"
#     file.write_text("")
#     return file


# @pytest.fixture
# def analyzer(project_root):
#     return ProjectManager(project_path=project_root, max_depth=5)


# @pytest.fixture(autouse=True)
# def project_structure(project_entrypoint):
#     workers_dir = project_entrypoint.parent / "workers"
#     managers_dir = project_entrypoint.parent / "managers"
#     workers_dir.mkdir(exist_ok=True)
#     managers_dir.mkdir(exist_ok=True)

#     worker_file = workers_dir / "worker.py"
#     worker_init = workers_dir / "__init__.py"
#     managers_file = managers_dir / "mana.py"
#     managers_init = managers_dir / "__init__.py"

#     for f in [worker_file, worker_init, managers_file, managers_init]:
#         f.write_text("")

#     return {
#         "workers_dir": workers_dir,
#         "managers_dir": managers_dir,
#         "worker_file": worker_file,
#         "worker_init": worker_init,
#         "managers_file": managers_file,
#         "managers_init": managers_init,
#     }
