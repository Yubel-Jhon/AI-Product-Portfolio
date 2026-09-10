"""把 SadTalker 的 croper.py 从 facexlib 版(extract_kp_videos_safe) 改成 face_alignment 版(extract_kp_videos)，
彻底绕开 facexlib/basicsr 依赖。在远端跑。
"""
path = '/root/autodl-tmp/SadTalker/src/utils/croper.py'
with open(path, encoding='utf-8') as f:
    s = f.read()

# 1. 换 import
s = s.replace(
    'from src.face3d.extract_kp_videos_safe import KeypointExtractor',
    'from src.face3d.extract_kp_videos import KeypointExtractor')

# 2. 删掉 facexlib import
s = s.replace('from facexlib.alignment import landmark_98_to_68\n', '')

# 3. 重写 get_landmark 方法体
old = '''        with torch.no_grad():
            dets = self.predictor.det_net.detect_faces(img_np, 0.97)

        if len(dets) == 0:
            return None
        det = dets[0]

        img = img_np[int(det[1]):int(det[3]), int(det[0]):int(det[2]), :]
        lm = landmark_98_to_68(self.predictor.detector.get_landmarks(img)) # [0]

        #### keypoints to the original location
        lm[:,0] += int(det[0])
        lm[:,1] += int(det[1])

        return lm'''
new = '''        with torch.no_grad():
            preds = self.predictor.detector.get_landmarks_from_image(img_np)
        if not preds or preds[0] is None:
            return None
        return preds[0].astype(np.float64)'''

assert old in s, 'get_landmark 方法体没匹配到！'
s = s.replace(old, new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(s)

ok = ('det_net' not in s) and ('landmark_98_to_68' not in s) \
     and ('get_landmarks_from_image' in s) and ('extract_kp_videos_safe' not in s)
print('patch croper.py:', 'OK' if ok else 'FAIL')
