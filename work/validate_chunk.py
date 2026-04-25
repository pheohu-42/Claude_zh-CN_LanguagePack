import json
import re
import sys

SOURCE = r"E:\download\Claude_zh-CN_LanguagePack\extracted-en-US\ion-dist\en-US.json"

LEFT_DQ = "“"  # Chinese left double quote
RIGHT_DQ = "”"  # Chinese right double quote
LBRACKET = "「"  # Japanese/Chinese left bracket
RBRACKET = "」"  # Japanese/Chinese right bracket

def load_source_keys():
    with open(SOURCE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def _strip_icu_blocks(text):
    """Remove ICU plural/select blocks from text to avoid false positives
    when extracting placeholders. ICU branch content like {step}/{steps}
    is translatable text, not placeholders to preserve."""
    # Iteratively remove nested ICU blocks (plural/select can nest)
    prev = None
    while prev != text:
        prev = text
        # Match {var, plural/select, ...} including nested braces
        # Simple approach: repeatedly strip the innermost ICU blocks
        text = re.sub(
            r'\{(\w+),\s*(plural|select)\s*,\s*[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
            '', text)
    return text

def extract_placeholders(text):
    cleaned = _strip_icu_blocks(text)
    results = set()
    for m in re.finditer(r'\{([a-zA-Z_]\w*)\}', cleaned):
        results.add(m.group(0))
    for m in re.finditer(r'%[sd]', text):
        results.add(m.group(0))
    return results

def extract_markup(text):
    results = set()
    for m in re.finditer(r'</?[a-zA-Z][a-zA-Z0-9]*[^>]*>', text):
        results.add(m.group(0))
    if '{br}' in text:
        results.add('{br}')
    return results

def extract_icu_vars(text):
    results = set()
    for m in re.finditer(r'\{(\w+),\s*(plural|select)', text):
        results.add(m.group(0))
    return results

def validate_chunk(source_data, translated_data, chunk_name="chunk"):
    errors = []
    src_keys = set(source_data.keys())
    trn_keys = set(translated_data.keys())

    if len(src_keys) != len(trn_keys):
        errors.append(f"Key count mismatch: source={len(src_keys)}, translated={len(trn_keys)}")

    missing = src_keys - trn_keys
    extra = trn_keys - src_keys
    if missing:
        errors.append(f"Missing keys: {list(missing)[:10]}{'...' if len(missing) > 10 else ''}")
    if extra:
        errors.append(f"Extra keys: {list(extra)[:10]}{'...' if len(extra) > 10 else ''}")

    for key in src_keys & trn_keys:
        src_val = source_data[key]
        trn_val = translated_data[key]

        if src_val.strip() and not trn_val.strip():
            errors.append(f"Key {key}: empty translated value (source was non-empty)")

        src_ph = extract_placeholders(src_val)
        trn_ph = extract_placeholders(trn_val)
        missing_ph = src_ph - trn_ph
        if missing_ph:
            errors.append(f"Key {key}: missing placeholders: {missing_ph}")

        src_mk = extract_markup(src_val)
        trn_mk = extract_markup(trn_val)
        missing_mk = src_mk - trn_mk
        if missing_mk:
            errors.append(f"Key {key}: missing markup: {missing_mk}")

        src_icu = extract_icu_vars(src_val)
        trn_icu = extract_icu_vars(trn_val)
        missing_icu = src_icu - trn_icu
        if missing_icu:
            errors.append(f"Key {key}: missing ICU vars: {missing_icu}")

    return errors

def fix_json_content(content):
    """Fix common JSON issues from translation output.
    Main issue: Chinese curly quotes "" get converted to ASCII double quotes ""
    by some agents, breaking JSON structure. We need to find these unescaped
    double quotes inside string values and replace them.
    Strategy: parse line by line, find value strings, fix unescaped quotes inside.
    """
    lines = content.split('\n')
    fixed_lines = []
    for line in lines:
        # Match JSON key-value lines: "key": "value",
        # We need to find the value portion and fix internal unescaped quotes
        m = re.match(r'^(\s*"[^"]*":\s*")(.*)(",?\s*)$', line)
        if m:
            prefix = m.group(1)  # "key": "
            value = m.group(2)   # the value content (may contain broken quotes)
            suffix = m.group(3)  # ", or "
            # Inside the value, replace any unescaped " with corner brackets
            # But we need to be careful not to touch already-escaped \"
            # Strategy: iterate chars, track escaping
            result = []
            i = 0
            while i < len(value):
                ch = value[i]
                if ch == '\\' and i + 1 < len(value):
                    # Escaped character, keep both
                    result.append(ch)
                    result.append(value[i + 1])
                    i += 2
                    continue
                if ch == '"':
                    # Unescaped double quote inside value - replace with corner bracket
                    result.append('「')  # 「
                elif ch == '“':  # Chinese left quote
                    result.append('「')
                elif ch == '”':  # Chinese right quote
                    result.append('」')  # 」
                else:
                    result.append(ch)
                i += 1
            fixed_lines.append(prefix + ''.join(result) + suffix)
        else:
            fixed_lines.append(line)
    return '\n'.join(fixed_lines)

def load_json_robust(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    try:
        return json.loads(content)
    except json.JSONDecodeError as first_err:
        fixed = fix_json_content(content)
        try:
            data = json.loads(fixed)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(fixed)
            print(f"  Fixed curly quotes in {filepath}")
            return data
        except json.JSONDecodeError as second_err:
            print(f"JSON parse failed even after fix: {second_err}")
            print(f"Original error: {first_err}")
            sys.exit(1)

def main():
    if len(sys.argv) < 3:
        print("Usage: python validate_chunk.py <source_chunk.json> <translated_chunk.json>")
        print("       python validate_chunk.py --full <translated_full.json>")
        sys.exit(1)

    source_data_full = load_source_keys()

    if sys.argv[1] == "--full":
        translated = load_json_robust(sys.argv[2])
        errors = validate_chunk(source_data_full, translated, "full file")
        if errors:
            print(f"VALIDATION FAILED ({len(errors)} errors):")
            for e in errors[:30]:
                print(f"  - {e}")
            if len(errors) > 30:
                print(f"  ... and {len(errors) - 30} more")
            sys.exit(1)
        else:
            print(f"VALIDATION PASSED: {len(translated)} entries OK")
            sys.exit(0)
    else:
        source_chunk_path = sys.argv[1]
        translated_path = sys.argv[2]

        source_chunk = load_json_robust(source_chunk_path)
        translated = load_json_robust(translated_path)

        errors = validate_chunk(source_chunk, translated)
        if errors:
            print(f"VALIDATION FAILED ({len(errors)} errors):")
            for e in errors[:30]:
                print(f"  - {e}")
            if len(errors) > 30:
                print(f"  ... and {len(errors) - 30} more")
            sys.exit(1)
        else:
            print(f"VALIDATION PASSED: {len(translated)} entries")
            sys.exit(0)

if __name__ == "__main__":
    main()