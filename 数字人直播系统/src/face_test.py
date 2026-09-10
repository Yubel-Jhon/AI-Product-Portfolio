"""远端测试：face.png 能不能被 face_alignment(FAN) 检出关键点。
检测不到 → SadTalker 处理不了这张动漫脸，需换方案。
"""
import cv2
import torch

import face_alignment

device = "cuda" if torch.cuda.is_available() else "cpu"
print("device =", device, "| cuda available:", torch.cuda.is_available())

fa = face_alignment.FaceAlignment(
    face_alignment.LandmarksType.TWO_D, flip_input=False, device=device
)

img = cv2.imread("/root/autodl-tmp/face.png")
if img is None:
    print("ERROR: 读不到 face.png")
    raise SystemExit(1)
h, w = img.shape[:2]
print("image =", w, "x", h)

preds = fa.get_landmarks_from_image(img)
if preds is None:
    print("RESULT: 未检测到人脸 (FAIL) —— SadTalker 会拒绝这张图")
else:
    print(f"RESULT: 检测到 {len(preds)} 张脸 (OK)，关键点 shape = {preds[0].shape}")
