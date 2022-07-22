###################
# import packages #
###################

import os, requests, uuid, json, time

from PIL import Image, ImageDraw
from io import BytesIO

# will need offline facial recognition for phase 2

from azure.cognitiveservices.vision.face import FaceClient
from azure.cognitiveservices.vision.face.models import TrainingStatusType, Person, QualityForRecognition

from msrest.authentication import CognitiveServicesCredentials

from azure.storage.blob import BlobServiceClient, ContainerClient, BlobClient

# from azure.cosmos import exceptions, CosmosClient, PartitionKey

##############################
# define important variables #
##############################

fileTypeList = [ ".JPG", ".PNG", ".BMP", ".GIF" ]

cogSvcEndpoint = ""
cogSvcSubKey = ""

saUrl = ""
saContainer = "images"

# SAS expires in 30 days from creation ( expiration date : 12-July-2022 )
saSasKey = ""

# first pass of images to match - list of face id's
facesDetected = []
facesToCompare = []

######################
# create connections #
######################

faceClient = FaceClient( cogSvcEndpoint, CognitiveServicesCredentials( cogSvcSubKey ) )

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
                return_face_landmarks = True, 
                # return_face_attributes = [ "blur", "noise", "exposure", "age", "gender", "hair", "accessories", "facialHair" ],
                recognition_model = "recognition_04" 
            )

            # print( detectedFaces )

            ####################################################
            # loop through in case multiple faces are detected #
            ####################################################

            for face in detectedFaces :

                # empty dictionary to be generated into JSON output
                jsonOutput = {}

                # print( face.face_attributes )
                # print( face.face_attributes.hair.hair_color[ 0 ] )

                # get face id
                currFaceId = face.face_id

                # append to batch list of faces detected for similarity comparison
                facesDetected.append( currFaceId )              

                jsonOutput[ "faceID" ] = currFaceId
                jsonOutput[ "imageFile" ] = ( saUrl + saContainer + "/" + blob[ "name" ] )
                
                # print( "Face ID: ", currFaceId )
                # print( "" )

                # collect rectangle points of face being reviewed
                # print( face.face_rectangle )
                faceRectangle = face.face_rectangle

                jsonOutput[ "imageLeft" ] = faceRectangle.left
                jsonOutput[ "imageTop" ] = faceRectangle.top
                jsonOutput[ "imageRight" ] = ( faceRectangle.left + faceRectangle.width )
                jsonOutput[ "imageBottom" ] = ( faceRectangle.top + faceRectangle.height )

                # attributes below no longer valid using most current detection model
                """# get estimated age
                approxAgeOfFace = face.face_attributes.age

                jsonOutput[ "approximateAge" ] = approxAgeOfFace

                # print( "Detected Age: ", approxAgeOfFace )
                # print( "" )

                # get gender
                approxGender = face.face_attributes.gender[ : ]

                jsonOutput[ "approximateGender" ] = approxGender

                # print( "Detected Gender: ", approxGender )
                # print( "" )

                # any accessories detected, including eyewear
                jsonOutput[ "detectedAccessories" ] = {}

                if len( face.face_attributes.accessories ) > 0 :

                    accessoryList = face.face_attributes.accessories

                    for accessory in accessoryList :

                        accDetails = {}

                        accId = "accId-" + str( uuid.uuid4() )

                        # accDetails[ "accesssoryID" ] = accId

                        # print( "Accessory Detected: ", accessory.type[ : ], "with confidence score of: ", accessory.confidence )
                        # print( type( accessory.type ) )

                        accDetails[ "type" ] = accessory.type[ : ]
                        accDetails[ "confidence" ] = accessory.confidence

                        jsonOutput[ "detectedAccessories" ][ accId ] = accDetails

                    # print( "" )

                # get facial hair
                facialHair = face.face_attributes.facial_hair

                # print( "Detected Facial Hair: ", facialHair )
                # print( "Moustache Confidence Score: ", facialHair.moustache )
                # print( "Beard Confidence Score: ", facialHair.beard )
                # print( "Sideburns Confidence Score: ", facialHair.sideburns )
                # print( "" )

                jsonOutput[ "moustacheConfidence" ] = facialHair.moustache
                jsonOutput[ "beardConfidence" ] = facialHair.beard
                jsonOutput[ "sideburnsConfidence" ] = facialHair.sideburns
                
                # return hair color items
                hairColorList = face.face_attributes.hair.hair_color

                for colorItem in hairColorList :

                    # print( colorItem )

                    if colorItem.confidence >= 0.5 :

                        hairColor = colorItem.color[ : ]
                        hcElement = hairColor + "-confidence"

                        jsonOutput[ hcElement ] = colorItem.confidence"""

                # print( jsonOutput )
                # print( "" )                

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

#####################################################################################################################
# face is detected - json output created                                                                            #
# loop back through images with detected faces                                                                      #
# compare for possible match                                                                                        #
#   1. create list of detected face id's                                                                            #
#   2. any 'similars' detected?                                                                                     #
#####################################################################################################################

for singleFace in facesDetected :

    # pass

    facesToCompare = facesDetected.pop( singleFace )

    # complete similarity check
    similarFaces = faceClient.face.find_similar( singleFace, facesToCompare )

    if similarFaces :

        # pass
        print( "Similar faces detected..." )

        for simiarFace in similarFaces :

            # if any matches are detected :
            #   a. check for an existing FaceGroup with a potential match
            #   b. if no FaceGroups exist with potential match, create new FaceGroup with detected matches
            pass
        
            

    else :

        print( "No matches detected..." )

    # empty list and start over
    facesToCompare = []