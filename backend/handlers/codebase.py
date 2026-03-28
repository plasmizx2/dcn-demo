"""Handler for codebase_review tasks."""

import requests
from ai.gemini_client import generate_text


def handle(task: dict, job: dict) -> str:
    """Review code from a public GitHub repo using Gemini."""
    github_url = job.get("input_payload", {}).get("github_url", "")
    task_desc = task.get("task_description", "")
    task_order = task.get("task_order", 1)

    if not github_url:
        # Fallback: use job title
        return generate_text(
            f"Provide a general codebase review checklist for: {job.get('title', 'a project')}"
        )

    # Parse owner/repo from GitHub URL
    # Handles: https://github.com/owner/repo or https://github.com/owner/repo.git
    parts = github_url.rstrip("/").rstrip(".git").split("github.com/")
    if len(parts) < 2:
        return generate_text(f"Review this project: {github_url}\n\n{task_desc}")

    owner_repo = parts[1]

    # Fetch repo file tree from GitHub API
    tree_resp = requests.get(
        f"https://api.github.com/repos/{owner_repo}/git/trees/main?recursive=1",
        headers={"Accept": "application/vnd.github.v3+json"},
        timeout=15,
    )

    # Try 'master' branch if 'main' fails
    if tree_resp.status_code != 200:
        tree_resp = requests.get(
            f"https://api.github.com/repos/{owner_repo}/git/trees/master?recursive=1",
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=15,
        )

    if tree_resp.status_code != 200:
        return generate_text(
            f"Could not fetch repo {github_url}. Provide a general code review for: {job.get('title', 'a project')}"
        )

    tree = tree_resp.json().get("tree", [])

    # Filter to important code files
    code_extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".cpp", ".c", ".h"}
    config_files = {"package.json", "requirements.txt", "Cargo.toml", "go.mod", "Dockerfile", "docker-compose.yml"}

    code_files = []
    config_list = []

    for item in tree:
        if item["type"] != "blob":
            continue
        path = item["path"]
        # Skip common junk
        if any(skip in path for skip in ["node_modules/", "vendor/", ".git/", "__pycache__/", "dist/", "build/"]):
            continue
        if any(path.endswith(ext) for ext in code_extensions):
            code_files.append(path)
        if path.split("/")[-1] in config_files:
            config_list.append(path)

    # Split files across 3 tasks:
    # Task 1 = core code files (first batch)
    # Task 2 = remaining code files
    # Task 3 = config + architecture overview
    if task_order == 1:
        files_to_review = code_files[:5]
    elif task_order == 2:
        files_to_review = code_files[5:10]
    else:
        files_to_review = config_list[:5]

    if not files_to_review:
        files_to_review = code_files[:3] if code_files else config_list[:3]

    # Fetch file contents
    file_contents = []
    for file_path in files_to_review[:5]:  # Cap at 5 files per task
        raw_resp = requests.get(
            f"https://raw.githubusercontent.com/{owner_repo}/main/{file_path}",
            timeout=10,
        )
        if raw_resp.status_code != 200:
            raw_resp = requests.get(
                f"https://raw.githubusercontent.com/{owner_repo}/master/{file_path}",
                timeout=10,
            )
        if raw_resp.status_code == 200:
            # Limit each file to first 200 lines to stay within token limits
            content = "\n".join(raw_resp.text.split("\n")[:200])
            file_contents.append(f"### {file_path}\n```\n{content}\n```")

    if not file_contents:
        return generate_text(
            f"Provide a general code review for the repo: {github_url}\n\n{task_desc}"
        )

    files_text = "\n\n".join(file_contents)

    prompt = (
        f"You are reviewing a public GitHub repository: {github_url}\n"
        f"Your assignment: {task_desc}\n\n"
        f"Here are the files to review:\n\n{files_text}\n\n"
        f"Provide a clear code review covering: code quality, potential bugs, "
        f"improvements, and best practices. Be specific and reference file names."
    )

    return generate_text(prompt)
