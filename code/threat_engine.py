import hashlib
import json
import math
import os
import re
import shutil
import time
from dataclasses import dataclass


@dataclass
class ScanResult:
    path: str
    score: int
    verdict: str
    reasons: list[str]
    sha256: str
    size: int


class LocalThreatEngine:
    """
    Lightweight local "AI-style" scoring engine.
    It combines several weak signals into a single risk score.
    """

    def __init__(self) -> None:
        risky_words = [
            "payload", "shellcode", "bypass", "crypter", "inject", "stealer",
            "keylogger", "backdoor", "ransom", "exploit", "dropper", "rat",
            "mimikatz", "cobalt", "metasploit", "phishing", "trojan", "malware",
        ]
        self.risky_pattern = re.compile(
            r"(" + "|".join(re.escape(w) for w in risky_words) + r")",
            re.IGNORECASE,
        )
        self.risky_extensions = {
            ".exe", ".dll", ".scr", ".bat", ".cmd", ".ps1", ".vbs", ".js",
            ".hta", ".jar", ".lnk", ".msi", ".com", ".pif",
        }

    def evaluate(self, path: str) -> ScanResult:
        reasons: list[str] = []
        score = 0
        filename = os.path.basename(path)
        extension = os.path.splitext(filename)[1].lower()

        if extension in self.risky_extensions:
            score += 25
            reasons.append(f"risky_extension:{extension}")

        if self.risky_pattern.search(filename):
            score += 25
            reasons.append("risky_keyword_in_name")

        double_ext = re.search(r"\.[a-z0-9]{1,4}\.[a-z0-9]{1,4}$", filename, re.IGNORECASE)
        if double_ext:
            score += 15
            reasons.append("double_extension")

        if len(filename) > 70:
            score += 10
            reasons.append("very_long_name")

        entropy = _shannon_entropy(filename.lower())
        if entropy >= 4.2:
            score += 20
            reasons.append("high_name_entropy")

        size = -1
        sha256 = ""
        if os.path.isfile(path):
            size = os.path.getsize(path)

            # Tiny script/executable droppers are common in incident response.
            if extension in {".exe", ".dll", ".js", ".vbs", ".ps1", ".bat", ".cmd"} and size < 40 * 1024:
                score += 20
                reasons.append("small_executable_or_script")

            sha256 = _sha256_file(path)
            if sha256 and (sha256.startswith("00") or sha256.startswith("dead")):
                score += 10
                reasons.append("hash_prefix_anomaly")

        verdict = "clean"
        if score >= 60:
            verdict = "malicious"
        elif score >= 35:
            verdict = "suspicious"

        return ScanResult(
            path=path,
            score=min(score, 100),
            verdict=verdict,
            reasons=reasons,
            sha256=sha256,
            size=size,
        )


class QuarantineManager:
    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir
        self.files_dir = os.path.join(base_dir, "files")
        self.meta_path = os.path.join(base_dir, "events.jsonl")
        os.makedirs(self.files_dir, exist_ok=True)

    def quarantine(self, path: str, result: ScanResult) -> tuple[bool, str]:
        if not os.path.exists(path):
            return False, "missing"

        ts = int(time.time())
        dst_name = f"{ts}_{os.path.basename(path)}"
        dst_path = os.path.join(self.files_dir, dst_name)

        try:
            shutil.move(path, dst_path)
            self._write_event("quarantined", path, dst_path, result)
            return True, dst_path
        except Exception as exc:
            self._write_event("quarantine_failed", path, "", result, error=str(exc))
            return False, str(exc)

    def _write_event(
        self,
        action: str,
        src_path: str,
        dst_path: str,
        result: ScanResult,
        error: str = "",
    ) -> None:
        event = {
            "timestamp": int(time.time()),
            "action": action,
            "src_path": src_path,
            "dst_path": dst_path,
            "score": result.score,
            "verdict": result.verdict,
            "reasons": result.reasons,
            "sha256": result.sha256,
            "size": result.size,
            "error": error,
        }
        with open(self.meta_path, "a", encoding="utf-8") as out:
            out.write(json.dumps(event, ensure_ascii=False) + "\n")


def _shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    entropy = 0.0
    length = len(value)
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def _sha256_file(path: str) -> str:
    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(64 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""
