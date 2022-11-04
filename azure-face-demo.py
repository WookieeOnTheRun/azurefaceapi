###################
# import packages #
###################

import os, requests, uuid, datetime, sys, time

from PIL import Image, ImageDraw
from io import BytesIO

from azure.cognitiveservices.vision.face import FaceClient
from azure.cognitiveservices.vision.face.models import TrainingStatusType, Person, QualityForRecognition

from msrest.authentication import CognitiveServicesCredentials

from azure.storage.blob import BlobServiceClient, BlobClient

##############################
# define important variables #
##############################

fileTypeList = [ ".JPG", ".PNG", ".BMP", ".GIF" ]

cogSvcEndpoint = ""
cogSvcSubKey = ""

saUrl = ""
saContainer = "images"

# SAS Token
saSasKey = ""

# first pass of images to match - list of face id's
facesDetected = {}
facesToCompare = []

######################
# create function(s) #
######################

# function to generate new PersonID
def fnCreatePersonID() :
    
    # add newly identified face to new face group
    currDate = datetime.datetime.now()
    currYear = str( currDate.year )
    currMonth = OneOrTwo( currDate.month )
    currDay = OneOrTwo( currDate.day )
    currHour = OneOrTwo( currDate.hour )
    currMinute = OneOrTwo( currDate.minute )
    currSecond = OneOrTwo( currDate.second )
    
    tempPersonId = "personId-" + currYear + currMonth + currDay + "-" + currHour + currMinute + currSecond
    
    return tempPersonId

# lambda function for use when building person id's
OneOrTwo = lambda x : "0" + str( x ) if ( x < 10 ) else str( x )

######################
# create connections #
######################

faceClient = FaceClient( cogSvcEndpoint, CognitiveServicesCredentials( cogSvcSubKey ) )

# clean up any created persongroups if used for testing
# get existing largefacegroups, clean up if needed ( for testing )

listPersonGroups = faceClient.person_group.list()

cleanUp = input( "Enter Y or N to delete any created person groups : " )

if cleanUp.upper() == "Y" :

    for persongroup in listPersonGroups :

        print( "Attempting to delete existing person group: ", str( persongroup.person_group_id ) )

        faceClient.person_group.delete( persongroup.person_group_id )

blobConn = BlobServiceClient( account_url = saUrl, credential = saSasKey )

contConn = blobConn.get_container_client( saContainer )

blobList = contConn.list_blobs()

for blob in blobList :

    # print( "Blob Name : ", blob[ "name" ] )

    ######################################
    # verify file extension is supported #
    ######################################
    fileSplit = os.path.splitext( blob[ "name" ] )

    fileExtension = fileSplit[ 1 ]

    if fileExtension.upper() in fileTypeList :

        blobUrl = saUrl + saContainer + "/" + blob[ "name" ] + saSasKey

        blobClientConn = BlobClient.from_blob_url( blobUrl )
        
        #######################################################
        # begin face detection for supported image file types #
        #######################################################

        try :

            print( "Passing to API : ", ( saUrl + saContainer + "/" + blob[ "name" ] ) )

            detectedFaces = faceClient.face.detect_with_url( 
                url = blobUrl, 
                # detection_model = "detection_04" ,
                return_face_landmarks = True, 
                # return_face_attributes = [ "blur", "noise", "exposure", "age", "gender", "hair", "accessories", "facialHair" ],
                recognition_model = "recognition_04"
            )

            # print( detectedFaces )

            ####################################################
            # loop through in case multiple faces are detected #
            ####################################################

            for face in detectedFaces :

                # get face id
                currFaceId = face.face_id

                # build string of URL for image location
                currFaceImg = ( saUrl + saContainer + "/" + blob[ "name" ] )
                
                # print( "Face ID: ", currFaceId )
                # print( "" )

                # collect rectangle points of face being reviewed
                # print( face.face_rectangle )
                faceRectangle = face.face_rectangle

                currFaceImgLeft = faceRectangle.left
                currFaceImgTop = faceRectangle.top
                currFaceImgRight = ( faceRectangle.left + faceRectangle.width )
                currFaceImgBottom = ( faceRectangle.top + faceRectangle.height )
                
                # add nested dictionary item for detected faceid, url and coordinates
                facesDetected[ currFaceId ] = {}
                facesDetected[ currFaceId ][ "URL" ] = currFaceImg
                facesDetected[ currFaceId ][ "ImageLeft" ] = currFaceImgLeft
                facesDetected[ currFaceId ][ "ImageTop"] = currFaceImgTop
                facesDetected[ currFaceId ][ "ImageRight" ] = currFaceImgRight
                facesDetected[ currFaceId ][ "ImageBottom" ] = currFaceImgBottom

                # display highlighted face within image - draw rectangle around face
                response = requests.get( blobUrl )
                
                img = Image.open( BytesIO( response.content ) )

                draw = ImageDraw.Draw( img )

                draw.rectangle( 
                    ( 
                        ( faceRectangle.left, faceRectangle.top ), 
                        ( 
                            ( faceRectangle.left + faceRectangle.width ), 
                            ( faceRectangle.top + faceRectangle.height ) 
                        ) 
                    ), outline = "red" )

                img.show()                

                img.close()


        except Exception as Ex :

            print( "Exception Generated: ", Ex )
            print( "" )    

    else :

        print( "Unsupported File Type for ", blob[ "name" ] )

#################################################
# face is detected - json output created        #
# loop back through images with detected faces  #
# compare for possible match                    #
#   1. create list of detected face id's        #
#   2. any 'similars' detected?                 #
#################################################
# get existing facegroups ( no large person groups created in this demo )

listFaceGroups = faceClient.person_group.list()

# create single list of FaceGroups and LargeFaceGroups to loop through
combinedFaceGroups = []

for fg in listFaceGroups :
    
    combinedFaceGroups.append( fg.person_group_id )

# print( "Detected Faces : ", facesDetected )
for dFace in facesDetected :
    
    print( "Detected Face Info : ", dFace )

# check for similarities between faces in images within this batch
# list must be passed to similarity method for faces to compare against ( face_ids )
for singleFace in facesDetected.keys() :

    # pass
    # print( singleFace )
    facesToCompare.append( singleFace )
    
for faceX in facesToCompare :
    
    # print( "Faces to Compare : ", facesToCompare )
    # print( "Attempting to Remove : ", faceX )

    xCompareFaces = facesToCompare.copy()
    xCompareFaces.remove( faceX )
    
    # print( facesToCompare )
    # print( xCompareFaces )

    # complete similarity check
    # face list cant be empty
    similarFaces = faceClient.face.find_similar( face_id = faceX, face_ids = xCompareFaces )

    if similarFaces :

        # pass
        print( "Similar faces detected..." )
        # print( similarFaces )

    #####################################################################################################
    # regardless if any similar matches are detected :                                                  #
    #   a. loop through existing PersonGroup(s) for a potential match                                   #
    #   b. if no PersonGroups exist with potential match, create new FaceGroup with detected face id    #
    #####################################################################################################
            
    # pass

    # counter variable to track the number of times an image was identified
    # based on an existing PersonGroup or LargePersonGroup
    addedToGroup = 0

    if len( combinedFaceGroups ) > 0 :         
            
        for facegroup in combinedFaceGroups :
            
            singleFaceList = []            
            singleFaceList.append( faceX )
                
            faceMatches = faceClient.face.identify( singleFaceList, person_group_id = facegroup, recognition_model = "recognition_04" )
                
            # print( faceMatches )
                
            for match in faceMatches :
                    
                # print( "Matches : ", match )
                    
                if len( match.candidates ) > 0 :
                    
                    for candidate in match.candidates :
                        
                        # print( candidate )
                        # grab person_id and confidence for adding to group below
                    
                        # pass
                        matchingPersonId = candidate.person_id
                        
                        if candidate.confidence >= .60 :
                            
                            # one more step - verification, just to make sure its the same person
                            verifyFace = faceClient.face.verify_face_to_person(
                                face_id = faceX ,
                                person_id = matchingPersonId ,
                                person_group_id = facegroup
                                )
                            
                            # print( verifyFace )
                            
                            if verifyFace.is_identical and verifyFace.confidence >= .60 :
        
                                # add Sas Key to URL string - prevent 409 error
                                uploadUrl = facesDetected[ faceX ][ "URL" ] + saSasKey
                
                                # add identified image to matching PersonGroup
                    
                                faceClient.person_group_person.add_face_from_url(
                                    person_group_id = facegroup, 
                                    person_id = matchingPersonId, 
                                    url = uploadUrl
                                    )
                    
                                # train the persongroup after addition
                                faceClient.person_group.train( person_group_id = facegroup )

                                # check to ensure training completion before moving on
                                while ( True ) :

                                    groupStatus = faceClient.person_group.get_training_status( facegroup )

                                    print( "Current Group Training Status :", groupStatus.status )

                                    if ( groupStatus.status is TrainingStatusType.succeeded ) :

                                        print( "Person Group Training has completed." )
                                        
                                        addedToGroup += 1

                                        break
                    
                                    elif ( groupStatus.status is TrainingStatusType.failed ) :

                                        faceClient.person_group.delete( facegroup )

                                        sys.exit( "Person Group Training has failed." )

                                        # wait 5 seconds before checking again
                                        time.sleep( 5 )                                
                                        
                            else :
                                
                                print( "Face Vertification failed or is not highly confident..." )
                                
                                break                            
                            
                        else :
                            
                            print( "Confidence score on match was below 60% threshold..." )
                    
    if addedToGroup == 0 or len( combinedFaceGroups ) == 0 :
                
        # pass
    
        print( "Creating PersonGroup for : ", faceX )
            
        # create new FaceGroup for image
        faceGroupId = str( uuid.uuid4() )
        faceGroupName = "persongroup" + faceGroupId
                
        faceClient.person_group.create( person_group_id = faceGroupId, name = faceGroupName, recognition_model = "recognition_04" )
                
        # add newly identified face to new face group
        try :
            
            newPersonId = fnCreatePersonID()
        
            personCreated = faceClient.person_group_person.create( person_group_id = faceGroupId,
                                                           name = newPersonId
                                                           )
        
            # add Sas Key to URL string - prevent 409 error
            uploadUrl = facesDetected[ faceX ][ "URL" ] + saSasKey
                
            faceClient.person_group_person.add_face_from_url( person_group_id = faceGroupId, 
                                                                  person_id = personCreated.person_id, 
                                                                  url = uploadUrl
                                                                  )        
                
            # train the persongroup after addition
            faceClient.person_group.train( person_group_id = faceGroupId )

            # check to ensure training completion before moving on
            while ( True ) :

                groupStatus = faceClient.person_group.get_training_status( faceGroupId )

                print( "Current Group Training Status :", groupStatus.status )

                if ( groupStatus.status is TrainingStatusType.succeeded ) :

                    print( "Person Group Training has completed." )

                    break
                
                elif ( groupStatus.status is TrainingStatusType.failed ) :

                    faceClient.person_group.delete( faceGroupId )

                    sys.exit( "Person Group Training has failed." )

                    # wait 5 seconds before checking again
                    time.sleep( 5 )
                    
            # update PersonGroup list variable
            listFaceGroups = faceClient.person_group.list()

            for fg in listFaceGroups :
                
                combinedFaceGroups.append( fg.person_group_id )
                    
        except Exception as Ex :
            
            print( "Exception Generated: ", Ex )
            print( "" )
            
            break

    """else :

        print( "No matches detected..." )"""
        
# Summary for Objects Created
print( "Summary of Person Group(s) Created : " )
for group in faceClient.person_group.list() :
    
    print( "Existing Person Group ID:", group.person_group_id, ", Name : ", group.name )
    
    for logicalPerson in faceClient.person_group_person.list( person_group_id = group.person_group_id ) :
        
        print( "Existing Logical Person ID : ", logicalPerson.person_id, ", Name : ", logicalPerson.name )
        # print( logicalPerson )