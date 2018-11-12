import numpy as np
import cv2
from segmentation import segment_characters_from_plate

class PlateDetector():
    def __init__(self, type_of_plate):
        if (type_of_plate == 'RECT_PLATE'):
            self.element_structure = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(22, 3))
            self.type_of_plate = 0
        if (type_of_plate== 'SQUARE_PLATE'):
            self.element_structure = cv2.getStructuringElement(shape=cv2.MORPH_RECT, ksize=(26, 5))
            self.type_of_plate = 1
        
    def find_possible_plates(self, input_img):
        self.input_img = input_img
        self.threshold_image = self.preprocess(input_img)
        self.extracted_contours = self.extract_contours(self.threshold_image)
        possible_plates = self.check_plate(input_img, self.extracted_contours)
        if(len(possible_plates) > 0):
            return possible_plates
        else:
            return None

    def find_characters_on_plate(self, plate):
        if (self.type_of_plate == 0): # rectangle plate
            charactersFound = segment_characters_from_plate(plate, 400)
            if charactersFound:
                return charactersFound
        elif (self.type_of_plate == 1): # square plate
            # divide the square plate into half to get a one line plate
            plate_upper = plate[0:plate.shape[0]/2, 0:plate.shape[1]]
            plate_lower = plate[plate.shape[0]/2: plate.shape[0], 0:plate.shape[1]]

            # get the characters of the upper plate and the lower plate
            upper_charactersFound = segment_characters_from_plate(plate_upper, 200)
            lower_charactersFound = segment_characters_from_plate(plate_lower, 200)
            if (upper_charactersFound and lower_charactersFound):
                charactersFound = upper_charactersFound + lower_charactersFound
                return charactersFound


    def preprocess(self, input_img):
        imgBlurred = cv2.GaussianBlur(input_img, (7, 7), 0) # old window was (5,5)
        gray = cv2.cvtColor(imgBlurred, cv2.COLOR_BGR2GRAY)
        sobelx = cv2.Sobel(gray, cv2.CV_8U, 1, 0, ksize=3)
        ret2,threshold_img = cv2.threshold(sobelx, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        return threshold_img
        
    def extract_contours(self, threshold_img):
        element = self.element_structure
        morph_img_threshold = threshold_img.copy()
        cv2.morphologyEx(src=threshold_img, op=cv2.MORPH_CLOSE, kernel=element, dst=morph_img_threshold)
        self.morphed_image = morph_img_threshold
        _, extracted_contours ,_ = cv2.findContours(morph_img_threshold, mode=cv2.RETR_EXTERNAL, method=cv2.CHAIN_APPROX_NONE)
        # if len(extracted_contours)!=0:
        #     print len(extracted_contours) #Test
        #     cv2.drawContours(self.input_img, extracted_contours, -1, (0,255,0), 1)
        #     cv2.imshow("Contours",self.input_img)
        #     cv2.waitKey(0)
        return extracted_contours
        
        # Rotate the plate
    def crop_rotated_contour(self, plate, rect): # crop the plate with its rotation
        box = cv2.boxPoints(rect)
        box = np.int0(box)
        W = rect[1][0]
        H = rect[1][1]
        
        Xs = [i[0] for i in box]
        Ys = [i[1] for i in box]
        x1 = min(Xs)
        x2 = max(Xs)
        y1 = min(Ys)
        y2 = max(Ys)
        
        angle = rect[2]
        if angle < (-45):
            angle += 90
        
        # If angle = 0, no need to rotate it
        if angle == 0:
            return plate

        # Center of rectangle in source image
        center = ((x1 + x2)/2,(y1 + y2)/2)

        # Size of the upright rectangle bounding the rotated rectangle
        size = (x2-x1, y2-y1)
        M = cv2.getRotationMatrix2D((size[0]/2, size[1]/2), angle, 1.0)

        # Cropped upright rectangle
        cropped = cv2.getRectSubPix(plate, size, center)
        cropped = cv2.warpAffine(cropped, M, size)
        croppedW = H if H > W else W
        croppedH = H if H < W else W

        # Final cropped & rotated rectangle
        croppedRotated = cv2.getRectSubPix(cropped, (int(croppedW), int(croppedH)), (size[0]/2, size[1]/2))
        return croppedRotated
        
    def clean_plate(self, plate):
        gray = cv2.cvtColor(plate, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        _, contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        
        if contours:
            areas = [cv2.contourArea(c) for c in contours]
            max_index = np.argmax(areas) # index of the largest contour in the area array
            
            max_cnt = contours[max_index]
            max_cntArea = areas[max_index]
            x,y,w,h = cv2.boundingRect(max_cnt)
            ratio = float(w)/float(h)

            if not ratioCheck(self.type_of_plate, max_cntArea, w, h):
                return plate, False, None
            rect = cv2.minAreaRect(contours[max_index])
            rotatedPlate = self.crop_rotated_contour(plate, rect)
            # print 'ratio = ',  ratio
            return rotatedPlate, True, [x, y, w, h]
        else:
            return plate, False, None

    def check_plate(self, input_img, contours):
        possible_plates = []
        self.corresponding_area = []
        self.char_on_plate = []
        for i, cnt in enumerate(contours):
            min_rect = cv2.minAreaRect(cnt)
            x,y,w,h = cv2.boundingRect(cnt)
            if validateRotationAndRatio(self.type_of_plate, min_rect):
                x,y,w,h = cv2.boundingRect(cnt)
                after_validation_img = input_img[y:y+h,x:x+w]

                ##### Use this for plates in tilt position ######
                # _rect = cv2.minAreaRect(cnt)
                # after_validation_img = crop_rotated_contour(img, _rect)
                # cv2.imshow('After validation', after_validation_img)
                # cv2.waitKey(0)
                ########################

                if(isMaxWhite(after_validation_img)):
                    after_clean_plate_img, plateFound, coordinates = self.clean_plate(after_validation_img)
                    if plateFound:
                        characters_on_plate = self.find_characters_on_plate(after_clean_plate_img)
                        if (characters_on_plate is not None and len(characters_on_plate) > 5):
                            possible_plates.append(after_clean_plate_img)
                            x1, y1, w1, h1 = coordinates
                            coordinates = x1+x, y1+y
                            self.corresponding_area.append(coordinates)
                            self.char_on_plate.append(characters_on_plate)
                        # possible_plates.append(after_clean_plate_img)
                        # x1, y1, w1, h1 = coordinates
                        # coordinates = x1+x, y1+y
                        # self.corresponding_area.append(coordinates)
        return possible_plates


######### PLATE FEATURES #########
# Check if a contour has the features of a plate
def ratioCheck(type_of_plate, area, width, height):
	if (type_of_plate == 0):
		aspect = 4.272727 # ratio of the rectangle Vietnamese plate.
		min = 3000  # minimum area of the plate
		max = 30000 # maximum area of the plate

		rmin = 3
		rmax = 7
	else:
		aspect = 1
		min = 4000
		max = 30000

		rmin = 0.5
		rmax = 1.5

	ratio = float(width) / float(height)
	if ratio < 1:
		ratio = 1 / ratio

	if (area < min or area > max) or (ratio < rmin or ratio > rmax):
		return False
	return True

# check the if the detected contour satisfies the white pixels by black pixels condition
def isMaxWhite(plate):
	avg = np.mean(plate)
	if(avg >= 40): # old value was 115, second chosen value was 90
		return True
	else:
 		return False

def validateRotationAndRatio(type_of_plate, rect):
	plate_type = type_of_plate
	(x, y), (width, height), rect_angle = rect

	if(width>height):
		angle = -rect_angle
	else:
		angle = 90 + rect_angle

	if angle > 15:
	 	return False

	if height == 0 or width == 0:
		return False

	area = height*width
	if not ratioCheck(plate_type, area,width,height):
		return False
	else:
		return True
