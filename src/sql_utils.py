"""SQL 文件解析工具：把 sql/*.sql 中按 `-- @name: xxx` 标注的语句解析成 {name: sql}。"""


def load_queries(path):
    queries = {}
    current = None
    buf = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("-- @name:"):
            if current:
                queries[current] = "\n".join(buf).strip()
            current = stripped.split(":", 1)[1].strip()
            buf = []
        else:
            buf.append(line)
    if current:
        queries[current] = "\n".join(buf).strip()
    return queries
