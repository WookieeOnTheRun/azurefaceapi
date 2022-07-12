###################
# import packages #
###################

import os, requests, uuid, json

import PIL, face_recognition # imported for potential long-term offline facial detection request

from azure.cognitiveservices.vision.face import FaceClient
from azure.cognitiveservices.vision.face.models import TrainingStatusType, Person, QualityForRecognition

from msrest.authentication import CognitiveServicesCredentials

from azure.storage.blob import BlobServiceClient, ContainerClient, BlobClient

from azure.cosmos import exceptions, CosmosClient, PartitionKey

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

cosmosEndpoint = ""
cosmosRwKey = ""
cosmosDb = "images"
cosmosCont = "metadata"

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

            print( "Passing to API : ", blobUrl )

            detectedFaces = faceClient.face.detect_with_url( 
                url = blobUrl, 
                return_face_landmarks = True, 
                return_face_attributes = [ "blur", "noise", "exposure", "age", "gender", "hair", "accessories", "facialHair" ],
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

                # ID column required for CosmosDB container using SQL API
                jsonOutput[ "id" ] = currFaceId

                # FaceID - being used as partition key
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

                # get estimated age
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

                        jsonOutput[ hcElement ] = colorItem.confidence

                # print( jsonOutput )
                # print( "" )

                #####################################
                # write output to CosmosDB instance #
                #####################################
                # cosmosJson = json.dumps( jsonOutput )

                # create CosmosDB connection instance
                # instance
                cosmosConn = CosmosClient( cosmosEndpoint, credential = cosmosRwKey )
                # database
                cosmosDbConn = cosmosConn.get_database_client( cosmosDb )
                # container
                cosmosContConn = cosmosDbConn.get_container_client( container = cosmosCont )

                # write item to container - accepts Python Dictionary
                try :

                    cosmosContConn.create_item( body = jsonOutput )

                    print( "Successfully addded item to CosmosDB..." )
                    print( "" )

                except Exception as CDbEx :

                    print( "Exception generated writing to CosmosDB: ", CDbEx )
                    print( "" )

                #########################################################################
                # create person group for comparison - filter for :                     #
                #   * not current face id                                               #
                #   * matching gender                                                   #
                # filtering within captured json results for :                          #
                #   * approximate age within 5 years                                    #                
                #   * matching approximate hair color within 10% confidence score match #
                #########################################################################
                matchQuery = 'select * from metadata x where x.faceID != "' + currFaceId + '" and x.approximateGender = "' + approxGender + '"'

                # first pass of images to match
                imagesToMatch = cosmosContConn.query_items(
                    query = matchQuery ,
                    enable_cross_partition_query = True
                )

                for image in imagesToMatch :

                    jsonImageInfo = json.dumps( image )
                    # print( jsonImageInfo )

                    # load into Python dictonary to allow search
                    imageJsonToDict = json.loads( jsonImageInfo )

                    # check if the determined age is within 5 years
                    if ( -5 <= ( approxAgeOfFace - imageJsonToDict[ "approximateAge" ] )  <= 5 ) :

                        # check if confidence score of hair color is within 10% difference
                        hairColorElementList = [ "black-confidence", "brown-confidence", "red-confidence", "blonde-confidence", "gray-confidence", "other-confidence" ]

                        for hairColor in hairColorElementList :

                            if hairColor in imageJsonToDict.keys() :

                                low = imageJsonToDict[ hairColor ] * 0.9
                                high = imageJsonToDict[ hairColor ] * 1.1

                                if low <= jsonOutput[ hairColor ] <= high :

                                    # add image to PersonGroup for matching
                                    print( "Adding image to PersonGroup..." )

                                else :

                                    pass

                    else :

                        pass

        except Exception as Ex :

            print( "Exception Generated: ", Ex )
            print( "" )

    else :

        print( "Unsupported File Type for ", blob[ "name" ] )