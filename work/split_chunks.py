import json
import os

SOURCE = r"E:\download\Claude_zh-CN_LanguagePack\extracted-en-US\ion-dist\en-US.json"
OUT_DIR = r"E:\download\Claude_zh-CN_LanguagePack\work"
CHUNK_SIZE = 250
CHAR_THRESHOLD = 25000  # if total value chars exceed this, shrink chunk

def main():
    with open(SOURCE, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = list(data.items())
    total = len(items)
    print(f"Total entries: {total}")

    chunks = []
    i = 0
    while i < total:
        chunk_size = CHUNK_SIZE
        # Check if default chunk would exceed char threshold
        end = min(i + chunk_size, total)
        char_count = sum(len(v) for _, v in items[i:end])
        if char_count > CHAR_THRESHOLD:
            chunk_size = 150
            end = min(i + chunk_size, total)

        chunk = dict(items[i:end])
        chunks.append((i, end, chunk))
        i = end

    print(f"Total chunks: {len(chunks)}")

    manifest = []
    for idx, (start, end, chunk) in enumerate(chunks, 1):
        fname = f"chunk_{idx:03d}.json"
        path = os.path.join(OUT_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chunk, f, ensure_ascii=False, indent=2)

        keys = list(chunk.keys())
        manifest.append({
            "chunk": idx,
            "file": fname,
            "start_index": start,
            "end_index": end,
            "count": end - start,
            "first_key": keys[0],
            "last_key": keys[-1],
        })

    manifest_path = os.path.join(OUT_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Manifest written to {manifest_path}")
    print("Done.")

if __name__ == "__main__":
    main()
