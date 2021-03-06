import cv2,urllib,sys,math, sys
import numpy as np
import inspect
from matplotlib import pyplot as plt

#FUNCTIONS
#executes first part of the program. i.e to find the difference between two frames
def getDifferenceHulls(imgFrame1,imgFrame2):
    #making duplicates of the above frames
    imgFrame1Copy = imgFrame1.copy()
    imgFrame2Copy = imgFrame2.copy()

    #changing the colorspace to grayscale
    imgFrame1Copy = cv2.cvtColor(imgFrame1Copy,cv2.COLOR_BGR2GRAY)
    imgFrame2Copy = cv2.cvtColor(imgFrame2Copy,cv2.COLOR_BGR2GRAY)

    #applying gaussianblur
    imgFrame1Copy = cv2.GaussianBlur(imgFrame1Copy,(5,5),0)
    imgFrame2Copy = cv2.GaussianBlur(imgFrame2Copy,(5,5),0)

    #finding the difference of the two frames and thresholding the diff
    imgDifference = cv2.absdiff(imgFrame1Copy,imgFrame2Copy)
    _,imgThresh = cv2.threshold(imgDifference,30,255,cv2.THRESH_BINARY)

    # cv2.imshow("imgThresh",imgThresh)

    # morphological operations: dilation and erosion
    kernel = np.ones((5,5),np.uint8)
    imgThresh = cv2.dilate(imgThresh,kernel,iterations = 1)
    imgThresh = cv2.dilate(imgThresh,kernel,iterations = 1)
    imgThresh = cv2.erode(imgThresh,kernel,iterations = 1)


    #finding contours of the thresholded image
    contours, hierarchy = cv2.findContours(imgThresh,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)

    #finding and drawing convex hulls
    hulls = []  #used to store hulls
    for cnt in contours:
        hulls.append(cv2.convexHull(cnt))

    return hulls

#draws the rectangles on the motion detected object
def drawBlobInfoOnImage(blobs,imgFrame2Copy):
    for i in range(len(blobs)):
        if (blobs[i].blnStillBeingTracked == True):
            rect_corner1 = (blobs[i].currentBoundingRect[0],blobs[i].currentBoundingRect[1])
            rect_corner2 = (blobs[i].currentBoundingRect[0]+blobs[i].width, blobs[i].currentBoundingRect[1]+blobs[i].height)

            # font settings
            intFontFace = cv2.FONT_HERSHEY_SIMPLEX;
            dblFontScale = blobs[i].dblCurrentDiagonalSize / 60.0
            intFontThickness = int(round(dblFontScale * 1.0))
            point = ((rect_corner1[0]+rect_corner2[0])/2,(rect_corner1[1]+rect_corner2[1])/2)

            # labels blob numbers
            cv2.putText(imgFrame2Copy, str(blobs[i].featureMatches), blobs[i].centerPositions[-1], intFontFace, dblFontScale, (0,255,0), intFontThickness);
            # draws box around the blob
            cv2.rectangle(imgFrame2Copy, rect_corner1,rect_corner2, (0,0,255))

#draws the contours on the image
def drawAndShowContours(imageSize,contours,strImageName):
    image = np.zeros(imageSize, dtype=np.uint8)
    cv2.drawContours(image, contours, -1,(255,255,255), -1)
    cv2.imshow(strImageName, image);

#draws the contours similar to the drawAndShowContours function
#but here the input provided is not the contours but object of class Blob
def drawAndShowBlobs(imageSize,blobs,strWindowsName):
    image = np.zeros(imageSize, dtype=np.uint8)
    contours = []
    for blob in blobs:
        if blob.blnStillBeingTracked == True:
            contours.append(blob.currentContour)

    cv2.drawContours(image, contours, -1,(255,255,255), -1);
    cv2.imshow(strWindowsName, image);

def findTarget(target,currentFrameBlobs):
    for blob in currentFrameBlobs:
        img_2 = target.copy()
        img_1 = blob.currentROI

        img1=cv2.cvtColor(img_1,cv2.COLOR_BGR2GRAY)
        img2=cv2.cvtColor(img_2,cv2.COLOR_BGR2GRAY)

        # Initiate SIFT detector
        sift = cv2.SIFT()

        # find the keypoints and descriptors with SIFT
        kp1, des1 = sift.detectAndCompute(img1,None)
        kp2, des2 = sift.detectAndCompute(img2,None)
        # print len(kp1),len(kp2)
        #FLANN
        FLANN_INDEX_KDTREE = 0
        index_params = dict(algorithm = FLANN_INDEX_KDTREE, trees = 5)
        search_params = dict(checks=50) # or pass empty dictionary
        flann = cv2.FlannBasedMatcher(index_params,search_params)
        try:
            matches = flann.knnMatch(des1,des2,k=2)
            variables=[i for i in dir(matches[0][0]) if not inspect.ismethod(i)]
            # Need to draw only good matches, so create a mask
            matchesMask = [[0,0] for i in xrange(len(matches))]

            rows1=img1.shape[0]
            cols1=img1.shape[1]
            rows2=img2.shape[0]
            cols2=img2.shape[1]
            out=np.zeros((max(rows1,rows2),cols1+cols2,1))
            out[:rows1,:cols1]=np.dstack([img1])
            out[:rows2,cols1:]=np.dstack([img2])
            count=0
            for i,(m,n) in enumerate(matches):
                if m.distance < 0.7*n.distance:
                    count += 1
            blob.featureMatches = count
            print blob.featureMatches

        except:
            return


#find the distance between two points p1 and p2
def distanceBetweenPoints(point1,point2):
    intX = abs(point1[0] - point2[0])
    intY = abs(point1[1] - point2[1])
    return math.sqrt(math.pow(intX, 2) + math.pow(intY, 2))

#matching algorithm to corelate two blob objects by matching it with the expected one
def matchCurrentFrameBlobsToExistingBlobs(existingBlobs,currentFrameBlobs):
    for existingBlob in existingBlobs:
        existingBlob.blnCurrentMatchFoundOrNewBlob = False
        existingBlob.predictNextPosition()


    for currentFrameBlob in currentFrameBlobs:
        intIndexOfLeastDistance = 0
        dblLeastDistance = 100000.0

        for i in range(len(existingBlobs)):
            if (existingBlobs[i].blnStillBeingTracked == True):
                dblDistance = distanceBetweenPoints(currentFrameBlob.centerPositions[-1], existingBlobs[i].predictedNextPosition)
                # print dblDistance
                if (dblDistance < dblLeastDistance):
                    dblLeastDistance = dblDistance
                    intIndexOfLeastDistance = i

        if (dblLeastDistance < currentFrameBlob.dblCurrentDiagonalSize * 3):     #1.15 origianal, 5
            addBlobToExistingBlobs(currentFrameBlob, existingBlobs, intIndexOfLeastDistance)
        else:
            addNewBlob(currentFrameBlob, existingBlobs)


    for existingBlob in existingBlobs:
        if (existingBlob.blnCurrentMatchFoundOrNewBlob == False):
            existingBlob.intNumOfConsecutiveFramesWithoutAMatch +=1;

        if (existingBlob.intNumOfConsecutiveFramesWithoutAMatch >= 5):
            existingBlob.blnStillBeingTracked = False;

#adds the details of the matching blob to the existingBlob
def addBlobToExistingBlobs(currentFrameBlob,existingBlobs,i):
    # print 'found continuos blob'

    existingBlobs[i].noOfTimesAppeared += 1
    existingBlobs[i].rois.append(currentFrameBlob.currentROI)
    existingBlobs[i].featureMatches += currentFrameBlob.featureMatches
    existingBlobs[i].noOfTimesAppeared += currentFrameBlob.noOfTimesAppeared

    existingBlobs[i].currentContour = currentFrameBlob.currentContour;
    existingBlobs[i].currentBoundingRect = currentFrameBlob.currentBoundingRect;

    existingBlobs[i].centerPositions.append(currentFrameBlob.centerPositions[-1])

    # if len(existingBlobs[i].centerPositions) > 30:
    #     del existingBlobs[i].centerPositions[0]

    existingBlobs[i].dblCurrentDiagonalSize = currentFrameBlob.dblCurrentDiagonalSize;
    existingBlobs[i].dblCurrentAspectRatio = currentFrameBlob.dblCurrentAspectRatio;

    existingBlobs[i].blnStillBeingTracked = True;
    existingBlobs[i].blnCurrentMatchFoundOrNewBlob = True;

#adds new blob to the list
def addNewBlob(currentFrameBlob,existingBlobs):
    currentFrameBlob.blnCurrentMatchFoundOrNewBlob = True
    existingBlobs.append(currentFrameBlob)


#CLASS
#class Blob consisting of variables and functions related to it
class Blob:
    #functions
    def printInfo(self):
        print 'area: '+str(self.area)+' Pos: '+str(self.centerPositions)

    def __init__(self, _contour,srcImage):
        self.centerPositions = []
        self.predictedNextPosition = [-1,-1]


        self.currentContour = _contour
        self.currentBoundingRect = cv2.boundingRect(self.currentContour)  #x,y,w,h
        x = (self.currentBoundingRect[0] + self.currentBoundingRect[0] + self.currentBoundingRect[2])/2
        y = (self.currentBoundingRect[1] + self.currentBoundingRect[1] + self.currentBoundingRect[3]) / 2
        self.currentCenter = (x,y)
        self.width = self.currentBoundingRect[2]
        self.height =  self.currentBoundingRect[3]
        self.area = self.currentBoundingRect[2] * self.currentBoundingRect[3]

        self.centerPositions.append(self.currentCenter)

        self.dblCurrentDiagonalSize = math.sqrt(math.pow(self.currentBoundingRect[2], 2) + math.pow(self.currentBoundingRect[3], 2));
        self.dblCurrentAspectRatio = float(self.currentBoundingRect[2])/float(self.currentBoundingRect[3])

        x,y,w,h = self.currentBoundingRect #x,y,w,h
        self.currentROI = srcImage[y:y+h, x:x+w]
        self.rois = []
        self.noOfTimesAppeared = 1
        self.featureMatches = 0

        # flags
        self.blnStillBeingTracked = True;
        self.blnCurrentMatchFoundOrNewBlob = True;

        self.intNumOfConsecutiveFramesWithoutAMatch = 0;

    def predictNextPosition(self):
        numPositions = len(self.centerPositions)
        if (numPositions == 1):
            self.predictedNextPosition[0] = self.centerPositions[-1][0]
            self.predictedNextPosition[1] = self.centerPositions[-1][1]

        elif (numPositions == 2):
            deltaX = self.centerPositions[1][0] - self.centerPositions[0][0]
            deltaY = self.centerPositions[1][1] - self.centerPositions[0][1]

            self.predictedNextPosition[0] = self.centerPositions[-1][0] + deltaX
            self.predictedNextPosition[1] = self.centerPositions[-1][1] + deltaY

        elif (numPositions == 3):
            sumOfXChanges = ((self.centerPositions[2][0] - self.centerPositions[1][1]) * 2) + \
            ((self.centerPositions[1][0] - self.centerPositions[0][0]) * 1)

            deltaX = int(round(float(sumOfXChanges)/3.0))

            sumOfYChanges = ((self.centerPositions[2][1] - self.centerPositions[1][1]) * 2) + \
            ((self.centerPositions[1][1] - self.centerPositions[0][1]) * 1)

            deltaY = int(round(float(sumOfYChanges) / 3.0))

            self.predictedNextPosition[0] = self.centerPositions[-1][0] + deltaX
            self.predictedNextPosition[1] = self.centerPositions[-1][1] + deltaY

        elif (numPositions == 4) :
            sumOfXChanges = ((self.centerPositions[3][0] - self.centerPositions[2][0]) * 3) + \
            ((self.centerPositions[2][0] - self.centerPositions[1][0]) * 2) + \
            ((self.centerPositions[1][0] - self.centerPositions[0][0]) * 1)

            deltaX = int(round(float(sumOfXChanges) / 6.0))

            sumOfYChanges = ((self.centerPositions[3][1] - self.centerPositions[2][1]) * 3) + \
            ((self.centerPositions[2][1] - self.centerPositions[1][1]) * 2) + \
            ((self.centerPositions[1][1] - self.centerPositions[0][1]) * 1)

            deltaY = int(round(float(sumOfYChanges) / 6.0))

            self.predictedNextPosition[0] = self.centerPositions[-1][0] + deltaX;
            self.predictedNextPosition[1] = self.centerPositions[-1][1] + deltaY;

        elif (numPositions >= 5):
            sumOfXChanges = ((self.centerPositions[numPositions - 1][0] - self.centerPositions[numPositions - 2][0]) * 4) + \
            ((self.centerPositions[numPositions - 2][0] - self.centerPositions[numPositions - 3][0]) * 3) + \
            ((self.centerPositions[numPositions - 3][0] - self.centerPositions[numPositions - 4][0]) * 2) + \
            ((self.centerPositions[numPositions - 4][0] - self.centerPositions[numPositions - 5][0]) * 1)

            deltaX = int(round(float(sumOfXChanges) / 10.0));

            sumOfYChanges = ((self.centerPositions[numPositions - 1][1] - self.centerPositions[numPositions - 2][1]) * 4) + \
            ((self.centerPositions[numPositions - 2][1] - self.centerPositions[numPositions - 3][1]) * 3) + \
            ((self.centerPositions[numPositions - 3][1] - self.centerPositions[numPositions - 4][1]) * 2) + \
            ((self.centerPositions[numPositions - 4][1] - self.centerPositions[numPositions - 5][1]) * 1)

            deltaY = int(round(float(sumOfYChanges) / 10.0))

            self.predictedNextPosition[0] = self.centerPositions[-1][0] + deltaX;
            self.predictedNextPosition[1] = self.centerPositions[-1][1] + deltaY;

        else:
            #should never get here
            pass

def detect_point(event,x,y,flags,param):
    if event == cv2.EVENT_LBUTTONDBLCLK:
        print (x,y)


#MAIN CODE
src = cv2.imread("database/img0.jpg")
cap = cv2.VideoCapture('video.avi')     #video file object
target = cv2.imread("database/img2215.jpg")

cv2.namedWindow("target",cv2.WINDOW_NORMAL)
cv2.imshow("target",target)

#checks if the video file is valid
if cap.isOpened():
    _,imgFrame1 = cap.read()   #capturing the first reference frame
else:
    sys.exit()

#variables used within the infinite loop
blnFirstFrame = True        #is true if the frame captured is first frame
blobs = []                  #holder for all the blobs

while cap.isOpened():

    #capturing second reference frame
    _,imgFrame2 = cap.read()

    if imgFrame2 is None:
        break

    #obtaining convex hulls and newly captured image
    hulls = getDifferenceHulls(imgFrame1,imgFrame2)

    #Blob validation
    currentFrameBlobs = []
    for hull in hulls:
        possibleBlob = Blob(hull,imgFrame2.copy())

        #conditions to approximate the blobs
        if (possibleBlob.area > 100 and \
        possibleBlob.dblCurrentAspectRatio >= 0.2 and \
        possibleBlob.dblCurrentAspectRatio <= 1.75 and \
        possibleBlob.width > 20 and \
        possibleBlob.height > 20 and \
        possibleBlob.dblCurrentDiagonalSize > 30.0 and \
        (cv2.contourArea(possibleBlob.currentContour) / float(possibleBlob.area)) > 0.40):
            currentFrameBlobs.append(possibleBlob)
        del possibleBlob
    #currentFrameBlobs contains blobs that are detected in the current frame

    #replacing the frame1 with frame2, so that newly captured frame can be stored in frame2
    imgFrame1 = imgFrame2.copy()

    #displaying any movement in the output screen
    img_current_blobs = imgFrame2.copy()
    img_all_blobs = imgFrame2.copy()
    # if(len(currentFrameBlobs) > 0):
    #     # drawAndShowBlobs(imgFrame2.shape,currentFrameBlobs,"imgCurrentFrameBlobs")
    #     drawBlobInfoOnImage(currentFrameBlobs,img_current_blobs)

    # finding match
    findTarget(target,currentFrameBlobs)

    # drawing current frame blobs with matches
    drawBlobInfoOnImage(currentFrameBlobs,img_current_blobs)


    #checks if the frame is the first frame of the video
    # MATCHING PROCESS
    if blnFirstFrame == True:
        for currentFrameBlob in currentFrameBlobs:
            blobs.append(currentFrameBlob)
    else:
        matchCurrentFrameBlobsToExistingBlobs(blobs,currentFrameBlobs)

    # blobs_active = 0
    # for blob in blobs:
    #     if blob.blnStillBeingTracked == True:
    #         blobs_active += 1
    #         color = tuple([int(c) for c in np.random.rand(3)*255])
    #         for pos in blob.centerPositions:
    #             cv2.circle(img_all_blobs,tuple(pos), 4, color, -1)
    #         font = cv2.FONT_HERSHEY_SIMPLEX
    #         cv2.line(img_all_blobs,tuple(blob.predictedNextPosition),blob.centerPositions[-1],color,2)


    # print '{} current, {} total'.format(len(currentFrameBlobs),len(blobs))

    cv2.imshow("current blobs",img_current_blobs)
    # cv2.imshow("All blobs",img_all_blobs)

    #flagging subsequent frames
    blnFirstFrame = False
    del currentFrameBlobs[:]    #clearing the currentFrameBlobs to capture newly formed blobs

    key_in = cv2.waitKey(5) & 0xFF
    if(key_in == ord('q')):
        break

print '\n\n\n\n################################################################'
print 'total no of blobs: {}'.format(len(blobs))

#deletes all the opened windows
cap.release()
cv2.destroyAllWindows()
