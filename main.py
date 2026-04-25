import os
import random
from github import Github, Auth

REPO_NAME = os.environ.get("REPO_NAME", "Egor213/Test-gen")
BASE_BRANCH = os.environ.get("BASE_BRANCH", "main")
TOKEN = os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    raise ValueError("GITHUB_TOKEN не задан")

random_num = random.randint(1, 1000000)
new_branch_name = f"test_{random_num}"

# Новая авторизация
g = Github(auth=Auth.Token(TOKEN))
repo = g.get_repo(REPO_NAME)
print(f"Репозиторий: {REPO_NAME}"
      f"\nБазовая ветка: {BASE_BRANCH}"
      f"\nТокен: {'ЗАДАН' if TOKEN else 'НЕ ЗАДАН'}")


# ---- Генерация имени новой ветки ----
random_num = random.randint(1, 1000000)
new_branch_name = f"test_{random_num}"

print(f"Создаём ветку {new_branch_name} от {BASE_BRANCH}...")

# ---- Получаем SHA последнего коммита в базовой ветке ----
base_branch_ref = repo.get_git_ref(f"heads/{BASE_BRANCH}")
base_sha = base_branch_ref.object.sha

# ---- Создаём новую ветку ----
repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=base_sha)
print(f"Ветка {new_branch_name} создана")

# ---- Создаём новый файл в этой ветке ----
file_name = f"test_{random_num}.txt"
file_content = f"Автоматический тест PR из ветки {new_branch_name}\nСлучайное число: {random_num}\n"

# Получаем текущее дерево базового коммита (чтобы добавить файл)
base_commit = repo.get_commit(base_sha)
base_tree = base_commit.commit.tree

# Создаём blob с содержимым файла
blob = repo.create_git_blob(content=file_content, encoding="utf-8")

# Создаём элемент дерева (файл)
element = {
    "path": file_name,
    "mode": "100644",   # обычный файл
    "type": "blob",
    "sha": blob.sha
}

# Создаём новое дерево, которое наследует всё из базового + новый файл
new_tree = repo.create_git_tree(tree=[element], base_tree=base_tree.sha)

# Создаём коммит
commit_message = f"Добавлен {file_name} из автоматического скрипта"
new_commit = repo.create_git_commit(
    message=commit_message,
    tree=new_tree,
    parents=[base_commit.commit]
)

# Обновляем ссылку новой ветки на созданный коммит
ref = repo.get_git_ref(f"heads/{new_branch_name}")
ref.edit(sha=new_commit.sha, force=False)
print(f"Файл {file_name} закоммичен в ветку {new_branch_name}")

# ---- Создаём Pull Request ----
pr_title = f"PR из ветки {new_branch_name} (автоматический тест)"
pr_body = "Этот PR создан автоматически через PyGithub."
pr = repo.create_pull(title=pr_title, body=pr_body, head=new_branch_name, base=BASE_BRANCH)
print(f"Pull Request создан: {pr.html_url}")