#!/usr/bin/env python3
import sys
import subprocess
import re
from pathlib import Path

try:
    import pymorphy2
except Exception:
    print("Ошибка: pymorphy2 не установлен. Установите: pip install pymorphy2 pymorphy2-dicts-ru")
    raise

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_\-']+")
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")

# Путь к Hunspell и словарю
HUNSPELL_PATH = r"C:\ProgramData\chocolatey\bin\hunspell.exe"
DICT_PATH = r"C:\Hunspell\ru_RU"

def load_whitelist(path="whitelist.txt"):
    p = Path(path)
    if not p.exists():
        return set()
    with p.open("r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip() and not line.strip().startswith("#")}

def hunspell_check_text(text):
    try:
        proc = subprocess.run(
            [HUNSPELL_PATH, "-d", DICT_PATH, "-l"],
            input=text,
            capture_output=True,
            text=True
        )
    except FileNotFoundError:
        print("Hunspell не найден — пропускаем орфопроверку.")
        return set()
    out = proc.stdout.strip()
    if not out:
        return set()
    return {w.strip() for w in out.splitlines() if w.strip()}

def find_occurrences(text, word):
    pat = re.compile(r"\b" + re.escape(word) + r"\b", flags=re.IGNORECASE | re.UNICODE)
    res = []
    for i, line in enumerate(text.splitlines(), 1):
        if pat.search(line):
            start = max(0, pat.search(line).start() - 20)
            end = min(len(line), pat.search(line).end() + 20)
            res.append((i, line[start:end].strip()))
    return res

def check_file(path: Path, whitelist):
    text = path.read_text(encoding="utf-8")
    print(f"\n=== Проверка файла: {path} ===")

    # Hunspell
    hun_words = hunspell_check_text(text)
    hun_filtered = {w for w in hun_words if w not in whitelist}
    if hun_filtered:
        print("Ошибки орфографии по Hunspell (после whitelist):")
        for w in sorted(hun_filtered):
            occ = find_occurrences(text, w)
            print(f" - {w} — {len(occ)} упоминания")
            for ln, sn in occ[:3]:
                print(f"    строка {ln}: {sn}")
    else:
        print("Hunspell: ошибок не найдено (после whitelist).")

    # pymorphy2
    morph = pymorphy2.MorphAnalyzer()
    seen = set()
    unknowns = []
    for i, line in enumerate(text.splitlines(), 1):
        for m in TOKEN_RE.finditer(line):
            tok = m.group(0)
            if tok in whitelist:
                continue
            key = tok.lower()
            if key in seen:
                continue
            seen.add(key)
            if not CYRILLIC_RE.search(tok):
                continue
            parsed = morph.parse(tok)
            if not parsed:
                unknowns.append((tok, i, "no parse"))
                continue
            p0 = parsed[0]
            tagstr = str(p0.tag)
            if "UNKN" in tagstr or getattr(p0.tag, "POS", None) is None:
                unknowns.append((tok, i, tagstr))
    if unknowns:
        print("Подозрительные/неопознанные формы (pymorphy2):")
        for tok, ln, tag in unknowns[:200]:
            print(f" - {tok} (строка {ln}) — tag: {tag}")
    else:
        print("pymorphy2: непонятных слов не найдено (по эвристике).")

def main(args):
    if not args:
        print("Использование: python spellcheck.py docs/*.md")
        sys.exit(1)
    whitelist = load_whitelist("whitelist.txt")
    files = []
    for pattern in args:
        files.extend(sorted(Path().glob(pattern)))
    if not files:
        print("Файлы не найдены по шаблонам:", args)
        sys.exit(1)
    for f in files:
        check_file(f, whitelist)

if __name__ == "__main__":
    main(sys.argv[1:])
