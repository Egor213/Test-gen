# import os
# from github import Github, Auth

# def main():
#     # GitHub токен из environment
#     token = os.environ.get("GITHUB_TOKEN")
#     if not token:
#         print("GITHUB_TOKEN not set")
#         return

#     g = Github(auth=Auth.Token(token))
#     # Параметры репозитория
#     repo_name = "Egor213/Test-gen"

#     repo = g.get_repo(repo_name)
#     print(repo)
#     # Получаем все открытые PR
#     prs = repo.get_pulls(state="open")
#     for pr in prs:
#         labels = [label.name for label in pr.get_labels()]
#         if "test" not in labels:
#             continue

#         print(f"\n=== PR #{pr.number}: {pr.title} by {pr.user.login} ===\n")

#         commits = pr.get_commits()
#         for commit in commits:
#             print(f"Commit SHA: {commit.sha}")
#             print(f"Author: {commit.commit.author.name}")
#             print(f"Message: {commit.commit.message.strip()}")
#             print("Files changed:")

#             for file in commit.files:
#                 print(f"  {file.filename} ({file.status})")
#                 if file.status != "removed":
#                     try:
#                         content = repo.get_contents(file.filename, ref=commit.sha)
#                         lines = content.decoded_content.decode().splitlines()
#                         snippet = "\n".join(lines)
#                         print(snippet)
#                     except Exception as e:
#                         print(f"    Could not read file: {e}")
#             print("-" * 50)
#         print("\nPR Review Comments:")
#         for comment in pr.get_review_comments():
#             print(f"File: {comment.path}")
#             print(f"Line: {comment.position}")
#             print(f"Author: {comment.user.login}")
#             print(f"Comment: {comment.body}")
#             print("-" * 30)

#         
#         print("\nPR General Comments:")
#         for comment in pr.get_issue_comments():
#             print(f"Author: {comment.user.login}")
#             print(f"Comment: {comment.body}")
#             print("-" * 30)

#         pr.create_issue_comment("Привет! Это комментарий, созданный скриптом ✅")

# if __name__ == "__main__":
#     main()
import argparse
from github import Github, Auth

def main():
    parser = argparse.ArgumentParser(description="Post a comment to a PR")
    parser.add_argument("--github-token", required=True, help="GitHub token for authentication")
    # parser.add_argument("--repo", required=True, help="Repository in the format owner/repo")
    # parser.add_argument("--pr-number", type=int, required=True, help="Pull Request number")
    # parser.add_argument("--comment", required=True, help="Comment text to post")
    args = parser.parse_args()
    print("123")
    token = args.github_token
    g = Github(auth=Auth.Token(token))
    repo_name = "Egor213/Test-gen"
    repo = g.get_repo(repo_name)
    prs = repo.get_pulls(state="open")
    for pr in prs:
        labels = [label.name for label in pr.get_labels()]
        if "test" not in labels:
            continue

        print(f"\n=== PR #{pr.number}: {pr.title} by {pr.user.login} ===\n")

        commits = pr.get_commits()
        for commit in commits:
            print(f"Commit SHA: {commit.sha}")
            print(f"Author: {commit.commit.author.name}")
            print(f"Message: {commit.commit.message.strip()}")
            print("Files changed:")
        pr.create_issue_comment("Hello world!")
if __name__ == "__main__":
    main()