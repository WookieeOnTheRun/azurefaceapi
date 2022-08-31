###################
# import packages #
###################

import os, requests, uuid, sys, datetime, time

from PIL import Image, ImageDraw
from io import BytesIO

import pandas as pd

# will need offline facial recognition for phase 2

from azure.cognitiveservices.vision.face import FaceClient
from azure.cognitiveservices.vision.face.models import TrainingStatusType, Person, QualityForRecognition

from msrest.authentication import CognitiveServicesCredentials

from azure.storage.blob import BlobServiceClient, ContainerClient, BlobClient

##############################
# define important variables #
##############################

fileTypeList = [ ".JPG", ".PNG", ".BMP", ".GIF" ]

cogSvcEndpoint = ""
cogSvcSubKey = ""

saUrl = ""
saContainer = "images"

# SAS for Storage Account Access
saSasKey = ""

# dataframe to capture detected images
facesDetected = pd.DataFrame( columns = [ "FaceId", "Image", "ImageLeft", "ImageRight", "ImageTop", "ImageBottom" ] )

# lambda function for use when building person id's
OneOrTwo = lambda x : "0" + str( x ) if ( x < 10 ) else str( x )

# track any FaceGroups created via this process
trackFaceGroups = []

######################
# create connections #
######################

faceClient = FaceClient( cogSvcEndpoint, CognitiveServicesCredentials( cogSvcSubKey ) )

# get existing largefacegroups, clean up if needed ( for testing )

listLargeFaceGroups = faceClient.large_person_group.list()

# clean up any created persongroups if used for testing
cleanUp = input( "Enter Y or N to delete any created person groups : " )

if cleanUp.upper() == "Y" :

    for largegroup in listLargeFaceGroups :

        print( "Attempting to delete existing large person group: ", str( largegroup.large_person_group_id ) )

        faceClient.large_person_group.delete( largegroup.large_person_group_id )

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

        try :

            print( "Passing to API : ", ( saUrl + saContainer + "/" + blob[ "name" ] ) )

            detectedFaces = faceClient.face.detect_with_url( 
                url = blobUrl, 
                detection_model = "detection_03" ,
                return_face_landmarks = True ,
                recognition_model = "recognition_04" 
            )

            # print( detectedFaces )

            ####################################################
            # loop through in case multiple faces are detected #
            ####################################################

            for face in detectedFaces :

                
                # print( face.face_attributes )
                # print( face.face_attributes.hair.hair_color[ 0 ] )

                # get face id
                currFaceId = face.face_id
                currImage = ( saUrl + saContainer + "/" + blob[ "name" ] )
                
                # print( "Face ID: ", currFaceId )
                # print( "" )

                # collect rectangle points of face being reviewed
                # print( face.face_rectangle )
                faceRectangle = face.face_rectangle

                currImageLeft = faceRectangle.left
                currImageTop = faceRectangle.top
                currImageRight = ( faceRectangle.left + faceRectangle.width )
                currImageBottom = ( faceRectangle.top + faceRectangle.height )                

                # record all detected faces in current batch
                facesDetected.loc[ len( facesDetected ) ] = [ currFaceId, currImage, currImageLeft, currImageRight, currImageTop, currImageBottom ]

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

print( facesDetected )

for i in range( len( facesDetected ) ) :

    # pass

    singleFace = facesDetected.iloc[ i, 0 ]
    singleFaceUrl = facesDetected.iloc[ i, 1 ]

    facesToCompare = facesDetected[ "FaceId" ].values.tolist()

    # remove current face from being compared with other detected faces
    facesToCompare.remove( singleFace )
        
    # print( facesToCompare )

    # complete similarity check
    # face list cant be empty
    similarFaces = faceClient.face.find_similar( face_id = singleFace, face_ids = facesToCompare )

    if similarFaces :

        # pass
        print( "Similar faces detected..." )

        for similarFace in similarFaces :

            # print( similarFace )

            ################################################################################################
            # if any similar matches are detected                                                          #
            #   a. loop through existing FaceGroup(s) for a potential match                                #
            #   b. if no FaceGroups exist with potential match, create new FaceGroup with detected face id #
            ################################################################################################
            
            # pass
            listLargeFaceGroups = faceClient.large_person_group.list()

            # counter variable to track the number of times an image was identified
            # based on an existing FaceGroup or LargeFaceGroup
            addedToGroup = 0

            if len( listLargeFaceGroups ) > 0 :
            
                for facegroup in listLargeFaceGroups :

                    print( facegroup )

                    simFaceIds = []
                    simFaceIds.append( similarFace.face_id )
                    print( simFaceIds )

                    fgPgId = facegroup.large_person_group_id
                    print( fgPgId )
                
                    faceMatches = faceClient.face.identify( simFaceIds, large_person_group_id = fgPgId )

                    if not faceMatches :

                        print( "No matches detected." )

                    else :
                
                        for match in faceMatches :
                    
                            # pass
                
                            print( "Candidate(s) :", match.candidates )

                            for candidate in match.candidates :
                
                                # add identified image to matching PersonGroup
                                currDate = datetime.datetime.now()
                                currYear = str( currDate.year )
                                currMonth = OneOrTwo( currDate.month )
                                currDay = OneOrTwo( currDate.day )
                                currHour = OneOrTwo( currDate.hour )
                                currMinute = OneOrTwo( currDate.minute )
                                currSecond = OneOrTwo( currDate.second )
                
                                newPersonId = "personid-" + currYear + currMonth + currDay + "-" + currHour + currMinute + currSecond

                                # create logical instance of a 'person' to add to persongroup
                                personCreated = faceClient.large_person_group_person.create( large_person_group_id = fgPgId, name = newPersonId )

                                # add sas to allow upload of image - prevent 409 error
                                uploadUrl = singleFaceUrl + saSasKey
                
                                # add image with detected face to person group with logical person ID
                                faceClient.large_person_group_person.add_face_from_url( large_person_group_id = fgPgId, person_id = personCreated.person_id, url = uploadUrl )

                                # train newly created persongroup
                                faceClient.large_person_group.train( large_person_group_id = fgPgId )

                                # check to ensure training completion before moving on
                                while ( True ) :

                                    groupStatus = faceClient.large_person_group.get_training_status( fgPgId )

                                    print( "Current Group Training Status :", groupStatus.status )

                                    if ( groupStatus.status is TrainingStatusType.succeeded ) :

                                        print( "Person Group Training has completed." )

                                        break
                    
                                    elif ( groupStatus.status is TrainingStatusType.failed ) :

                                        faceClient.large_person_group.delete( faceGroupId )

                                        sys.exit( "Person Group Training has failed." )

                                    # wait 5 seconds before checking again
                                    time.sleep( 5 )
                    
                        # counter to track group(s) image is added to
                        addedToGroup += 1
                    
            if addedToGroup == 0 or len( listLargeFaceGroups ) == 0 :
                
                # pass
            
                # create new PersonGroup for image
                faceGroupId = str( uuid.uuid4() )
                faceGroupName = "large-persongroup-" + faceGroupId
                
                faceClient.large_person_group.create( large_person_group_id = faceGroupId, name = faceGroupName, recognition_model = "recognition_04" )
                
                # add newly identified face to new face group
                currDate = datetime.datetime.now()
                currYear = str( currDate.year )
                currMonth = OneOrTwo( currDate.month )
                currDay = OneOrTwo( currDate.day )
                currHour = OneOrTwo( currDate.hour )
                currMinute = OneOrTwo( currDate.minute )
                currSecond = OneOrTwo( currDate.second )
                
                newPersonId = "personid-" + currYear + currMonth + currDay + "-" + currHour + currMinute + currSecond

                # create logical instance of a 'person' to add to persongroup
                personCreated = faceClient.large_person_group_person.create( large_person_group_id = faceGroupId, name = newPersonId )

                # add sas to allow upload of image - prevent 409 error
                uploadUrl = singleFaceUrl + saSasKey
                
                # add image with detected face to person group with logical person ID
                faceClient.large_person_group_person.add_face_from_url( large_person_group_id = faceGroupId, person_id = personCreated.person_id, url = uploadUrl )

                # train newly created persongroup
                faceClient.large_person_group.train( large_person_group_id = faceGroupId )

                # check to ensure training completion before moving on
                while ( True ) :

                    groupStatus = faceClient.large_person_group.get_training_status( faceGroupId )

                    print( "Current Group Training Status :", groupStatus.status )

                    if ( groupStatus.status is TrainingStatusType.succeeded ) :

                        print( "Person Group Training has completed." )

                        break
                    
                    elif ( groupStatus.status is TrainingStatusType.failed ) :

                        faceClient.large_person_group.delete( faceGroupId )

                        sys.exit( "Person Group Training has failed." )

                    # wait 5 seconds before checking again
                    time.sleep( 5 )

                # add record for persongroup
                print( "Large Person Group(s) Added and Trained So Far : ", ( faceClient.large_person_group.list() ) )

    else :

        print( "No matches detected..." )

    # empty list and start over
    facesToCompare = []