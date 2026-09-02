import re
from typing import List

def format_sql_for_display(sql: str) -> str:
    """
    Formats SQL queries into professional multi-line vertical representation
    for UI and PDF display without modifying the original executed query logic.
    """
    if not sql or not sql.strip():
        return ""

    raw_sql = sql.strip()
    has_semicolon = raw_sql.endswith(";")
    text_to_format = raw_sql[:-1].strip() if has_semicolon else raw_sql

    # Tokenizer pattern:
    # 1. Single-quoted strings: '...'
    # 2. Double-quoted identifiers: "..."
    # 3. Punctuation: , ; ( )
    # 4. Words / symbols
    token_pattern = re.compile(
        r"('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|[,;()]|[^\s,;()'\"]+)",
        re.IGNORECASE
    )

    tokens = token_pattern.findall(text_to_format)
    if not tokens:
        return sql

    major_clauses = [
        "SELECT DISTINCT", "SELECT",
        "FROM",
        "WHERE",
        "GROUP BY",
        "HAVING",
        "ORDER BY",
        "LIMIT",
        "OFFSET",
        "INNER JOIN", "LEFT JOIN", "RIGHT JOIN", "FULL JOIN", "CROSS JOIN", "JOIN",
        "UNION ALL", "UNION"
    ]

    sql_keywords = {
        "SELECT", "DISTINCT", "FROM", "WHERE", "GROUP", "BY", "ORDER", "HAVING",
        "LIMIT", "OFFSET", "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "CROSS", "ON",
        "AS", "AND", "OR", "ASC", "DESC", "CASE", "WHEN", "THEN", "ELSE", "END",
        "IS", "NULL", "NOT", "IN", "LIKE", "EXISTS", "BETWEEN", "UNION", "ALL",
        "COUNT", "SUM", "AVG", "MIN", "MAX", "TRIM", "LOWER", "UPPER", "COALESCE", "ROUND", "CAST"
    }

    # Step 1: Normalize tokens & uppercase keywords
    norm_tokens = []
    idx = 0
    while idx < len(tokens):
        tok = tokens[idx]
        next_tok = tokens[idx + 1] if idx + 1 < len(tokens) else ""
        two_word = f"{tok.upper()} {next_tok.upper()}"

        if two_word in major_clauses:
            norm_tokens.append(two_word)
            idx += 2
            continue

        if tok.startswith("'") or tok.startswith('"'):
            norm_tokens.append(tok)
        elif tok.upper() in sql_keywords:
            norm_tokens.append(tok.upper())
        else:
            norm_tokens.append(tok)
        idx += 1

    # Check if simple short query
    join_single = " ".join(norm_tokens)
    join_clean = re.sub(r'\s+,', ',', join_single)
    join_clean = re.sub(r'(\b\w+)\s+\(', r'\1(', join_clean)
    join_clean = re.sub(r'\(\s+', '(', join_clean)
    join_clean = re.sub(r'\s+\)', ')', join_clean)

    has_complex_clauses = any(c in norm_tokens for c in ["WHERE", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "JOIN", "INNER JOIN", "LEFT JOIN"])
    is_simple_short = len(join_clean) < 45 and not has_complex_clauses and norm_tokens.count(",") == 0

    if is_simple_short:
        res = join_clean
        if has_semicolon:
            res += ";"
        return res

    # Step 2: Clause-based formatting
    lines: List[str] = []
    curr_line: List[str] = []
    curr_clause = ""
    paren_depth = 0

    def flush_line(indent_spaces=4):
        nonlocal curr_line
        if curr_line:
            line_str = " ".join(curr_line).strip()
            line_str = re.sub(r'\s+,', ',', line_str)
            line_str = re.sub(r'(\b\w+)\s+\(', r'\1(', line_str)
            line_str = re.sub(r'\(\s+', '(', line_str)
            line_str = re.sub(r'\s+\)', ')', line_str)
            prefix = " " * indent_spaces if indent_spaces > 0 else ""
            lines.append(prefix + line_str)
            curr_line = []

    i = 0
    while i < len(norm_tokens):
        t = norm_tokens[i]

        if t == "(":
            paren_depth += 1
            curr_line.append(t)
            i += 1
            continue
        elif t == ")":
            paren_depth = max(0, paren_depth - 1)
            curr_line.append(t)
            i += 1
            continue

        # Major Clause Trigger (at paren_depth 0)
        if paren_depth == 0 and t in major_clauses:
            indent_for_prev = 4 if curr_clause in ["SELECT", "SELECT DISTINCT"] else 0
            flush_line(indent_spaces=indent_for_prev)
            curr_clause = t
            curr_line.append(t)

            if t in ["FROM", "LIMIT", "OFFSET"] and i + 1 < len(norm_tokens) and norm_tokens[i+1] not in major_clauses:
                curr_line.append(norm_tokens[i+1])
                i += 2
                flush_line(indent_spaces=0)
                continue
            elif t == "WHERE" and i + 1 < len(norm_tokens) and norm_tokens[i+1] not in major_clauses:
                # Keep first condition on same line as WHERE
                # collect tokens until next AND/OR or major clause
                idx_j = i + 1
                while idx_j < len(norm_tokens) and norm_tokens[idx_j] not in major_clauses and norm_tokens[idx_j] not in ["AND", "OR"]:
                    curr_line.append(norm_tokens[idx_j])
                    idx_j += 1
                i = idx_j
                flush_line(indent_spaces=0)
                continue
            elif t in ["GROUP BY", "ORDER BY"] and i + 1 < len(norm_tokens):
                remaining = norm_tokens[i+1:]
                has_comma_in_clause = False
                for r_tok in remaining:
                    if r_tok in major_clauses:
                        break
                    if r_tok == ",":
                        has_comma_in_clause = True
                        break
                if not has_comma_in_clause:
                    idx_j = i + 1
                    while idx_j < len(norm_tokens) and norm_tokens[idx_j] not in major_clauses:
                        curr_line.append(norm_tokens[idx_j])
                        idx_j += 1
                    i = idx_j
                    flush_line(indent_spaces=0)
                    continue
                else:
                    flush_line(indent_spaces=0)
                    i += 1
                    continue
            else:
                flush_line(indent_spaces=0)
                i += 1
                continue

        # Item/Condition separators at paren_depth 0
        if paren_depth == 0:
            if curr_clause in ["SELECT", "SELECT DISTINCT"] and t == ",":
                curr_line.append(",")
                flush_line(indent_spaces=4)
                i += 1
                continue
            elif curr_clause == "WHERE" and t in ["AND", "OR"]:
                flush_line(indent_spaces=4)
                curr_line.append(t)
                i += 1
                continue
            elif curr_clause in ["GROUP BY", "ORDER BY"] and t == ",":
                curr_line.append(",")
                flush_line(indent_spaces=4)
                i += 1
                continue
            elif "JOIN" in curr_clause and t == "ON":
                flush_line(indent_spaces=4)
                curr_line.append(t)
                i += 1
                continue

        curr_line.append(t)
        i += 1

    if curr_line:
        indent = 4 if curr_clause in ["SELECT", "SELECT DISTINCT"] else 0
        flush_line(indent_spaces=indent)

    # Post-process final lines
    final_lines = []
    for line in lines:
        body_part = line.rstrip()
        indent_match = re.match(r'^(\s*)', line)
        indent_str = indent_match.group(1) if indent_match else ""
        text_part = body_part.strip()
        text_part = re.sub(r'\s+,', ',', text_part)
        text_part = re.sub(r'(\b\w+)\s+\(', r'\1(', text_part)
        text_part = re.sub(r'\(\s+', '(', text_part)
        text_part = re.sub(r'\s+\)', ')', text_part)
        final_lines.append(indent_str + text_part)

    result = "\n".join(final_lines)
    if has_semicolon:
        result += ";"

    return result
