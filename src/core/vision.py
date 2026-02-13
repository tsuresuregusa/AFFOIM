import cv2
import numpy as np

class VisionProcessor:
    @staticmethod
    def detect_violin_body(image_path: str, view_type='front'):
        """
        Detects the bounding box of the violin body.
        Uses a robust vertical width-profile analysis to find the 'bulge' of the body
        and ignore the 'stick' of the neck.
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None
            
            # Preprocessing
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Thresholding: Try both standard and inverted to be robust to background
            _, thresh1 = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            _, thresh2 = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Pick the one with the more "central" mass (heuristic for subject vs background)
            if np.mean(thresh1[:, img.shape[1]//4:3*img.shape[1]//4]) > np.mean(thresh1):
                thresh = thresh1
            else: thresh = thresh2
            
            # Cleanup: Stricter for side view to remove neck/scroll
            k_size = 9 if view_type == 'side' else 5
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            if view_type == 'side':
                # Morphological opening to explicitly remove thin structures like strings/neck
                open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, open_kernel)
            
            # Calculate vertical width profile
            width_profile = np.sum(thresh, axis=1) / 255
            
            # Smooth the profile
            if len(width_profile) < 50: return None
            smooth_profile = np.convolve(width_profile, np.ones(31)/31, mode='same')
            
            max_w = np.max(smooth_profile)
            if max_w < 10: return None
            
            # Thresholding: The body is bulky. Neck is thin.
            # Use a threshold that specifically finds the "bulge".
            is_body = smooth_profile > (0.6 * max_w)
            
            from scipy.ndimage import label
            labels, num_features = label(is_body)
            if num_features == 0: return None
            
            # Pick the largest region that is NOT the whole image
            # Violins in upright photos usually occupy 60-80% of height.
            regions = []
            for i in range(1, num_features + 1):
                y_idx = np.where(labels == i)[0]
                h_reg = y_idx[-1] - y_idx[0]
                if h_reg < 50: continue # Too small
                # Removed max-height check to allow full-frame violin bodies
                # if h_reg > 0.99 * img.shape[0]: continue 
                
                integral = np.sum(smooth_profile[y_idx])
                regions.append((integral, y_idx[0], y_idx[-1]))
            
            if not regions: return None
            
            # Best region is the one with most mass (Bulge)
            best_region = max(regions, key=lambda x: x[0])
            y_start, y_end = best_region[1], best_region[2]
            
            # Clip 10% from top/bottom to be safe from curves trailing into neck
            h_actual = y_end - y_start
            y_start += int(0.05 * h_actual)
            y_end -= int(0.05 * h_actual)
            
            # Horizontal Bounds
            body_mask = thresh[y_start:y_end, :]
            x_sum = np.sum(body_mask, axis=0)
            x_indices = np.where(x_sum > 0)[0]
            if len(x_indices) < 5: return None
            
            x_start, x_end = x_indices[0], x_indices[-1]
            return (int(x_start), int(y_start), int(x_end - x_start), int(y_end - y_start))
            
        except Exception as e:
            return None
