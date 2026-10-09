"""B 模块：用 Gemini 视觉 API 判断画面中的人是否直视摄像头。

约定：yes = 明确看向摄像头（台灯应熄灭）；no = 其他情况。
输入可以是 A 模块输出的 JPEG base64，也可以是完整的 data URL。
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_MODEL = "gemini-3.8-flash"
PROMPT = (
    "Look at the main person's eyes in this webcam image. "
    "Is the person clearly looking directly toward the camera lens? "
    "Reply with exactly one lowercase word: yes or no. "
    "Reply yes only when the gaze is clearly toward the lens. "
    "If there is no visible face, the eyes are obscured, there are multiple people "
    "and no clear main person, or the direction is uncertain, reply no."
)


class BrainError(Exception):
    """API 调用或结果解析失败；不能把失败当作 yes。"""


def _image_data(image_base64: str, mime_type: str) -> tuple[str, str]:
    if image_base64.startswith("data:"):
        header, sep, payload = image_base64.partition(",")
        if not sep or ";base64" not in header:
            raise ValueError("图片 data URL 必须包含 base64 数据")
        mime_type = header.removeprefix("data:").split(";", 1)[0]
    else:
        payload = image_base64

    if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("支持 JPEG、PNG 或 WebP 图片")

    try:
        image_bytes = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("图片不是有效的 base64 数据") from exc
    if not image_bytes:
        raise ValueError("图片数据为空")
    return payload, mime_type


def _answer(response: dict) -> str:
    if response.get("status") != "completed":
        raise BrainError(f"Gemini 判断未完成：{response.get('status', 'unknown')}")
    texts = [
        content.get("text", "")
        for step in response.get("steps", [])
        if step.get("type") == "model_output"
        for content in step.get("content", [])
        if content.get("type") == "text"
    ]
    raw = " ".join(texts).strip().lower()
    if re.fullmatch(r"[\s\"']*(yes|no)[\s.\"']*", raw):
        return raw.strip(" \t\r\n.\"'")
    raise BrainError(f"模型没有返回单独的 yes/no：{raw[:100]!r}")


def analyze_image(
    image_base64: str,
    *,
    mime_type: str = "image/jpeg",
    model: str = DEFAULT_MODEL,
    timeout: float = 30.0,
    api_key: str | None = None,
) -> tuple[str, float]:
    """返回 (yes/no, API 调用耗时秒数)。"""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise BrainError("请先设置 GEMINI_API_KEY 环境变量（Google AI Studio 的密钥）")

    image_data, image_mime = _image_data(image_base64, mime_type)
    payload = {
        "model": model,
        "store": False,
        "input": [
            {"type": "text", "text": PROMPT},
            {"type": "image", "data": image_data, "mime_type": image_mime},
        ],
        "generation_config": {"thinking_level": "low"},
    }
    request = Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "x-goog-api-key": key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout) as reply:
            response = json.load(reply)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise BrainError(f"Gemini API 返回 HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise BrainError(f"连接 API 失败：{exc}") from exc

    elapsed = time.perf_counter() - started
    return _answer(response), elapsed


def is_looking(frame: str) -> bool:
    """供主程序调用：A 模块的 JPEG base64 -> 是否明确看向摄像头。"""
    answer, elapsed = analyze_image(frame)
    print(f"B 模块：{answer}，API 耗时 {elapsed:.2f} 秒")
    return answer == "yes"


def analyze_file(path: Path, *, model: str = DEFAULT_MODEL) -> tuple[str, float]:
    mime_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    mime_type = mime_types.get(path.suffix.lower())
    if mime_type is None:
        raise ValueError(f"不支持的图片格式：{path}")
    image_base64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return analyze_image(image_base64, mime_type=mime_type, model=model)


def main() -> int:
    parser = argparse.ArgumentParser(description="判断是否看向摄像头；yes 表示台灯应熄灭")
    parser.add_argument("image", nargs="?", type=Path, help="单张 JPG、PNG 或 WebP 图片")
    parser.add_argument("--test-dir", type=Path, help="测试目录，内含 yes/ 和 no/ 两个子目录")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"视觉模型，默认 {DEFAULT_MODEL}")
    args = parser.parse_args()

    if (args.image is None) == (args.test_dir is None):
        parser.error("请提供单张图片，或使用 --test-dir 指定测试目录")

    if args.image is not None:
        try:
            answer, elapsed = analyze_file(args.image, model=args.model)
        except (BrainError, OSError, ValueError) as exc:
            print(f"错误：{exc}", file=sys.stderr)
            return 1
        print(f"{answer}  耗时 {elapsed:.2f} 秒")
        return 0

    images = [
        (path, expected)
        for expected in ("yes", "no")
        for path in sorted((args.test_dir / expected).glob("*"))
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    if not images:
        print("没有找到测试图片。请放到 yes/ 和 no/ 子目录。", file=sys.stderr)
        return 1

    correct = 0
    durations = []
    errors = 0
    for path, expected in images:
        started = time.perf_counter()
        try:
            answer, elapsed = analyze_file(path, model=args.model)
        except (BrainError, OSError, ValueError) as exc:
            errors += 1
            print(f"{path}: 错误：{exc}  耗时={time.perf_counter() - started:.2f} 秒")
            continue
        correct += answer == expected
        durations.append(elapsed)
        mark = "✓" if answer == expected else "✗"
        print(f"{mark} {path}: 标注={expected}  预测={answer}  耗时={elapsed:.2f} 秒")

    print(f"准确率：{correct}/{len(images)} = {correct / len(images):.1%}")
    if durations:
        print(f"成功调用的平均耗时：{sum(durations) / len(durations):.2f} 秒")
    if errors:
        print(f"失败调用：{errors} 次（计入准确率分母）")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
