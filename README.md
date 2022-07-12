# azurefaceapi
Using Azure Cognitive Services Face API to detect faces ( Phase 1 ) and match faces ( Phase 2 )

The script currently connects to an Azure Blob Storage Account and loops through supported image files to detect faces, as well as extract metadata. A custom metadata extraction is created and written to a Cosmos DB instance for faster tracking ( Phase 1 ). This will be removed eventually, instead using FaceGroups within Cognitive Services.

This script will be evolving over time to take metadata changes enforced by Microsoft into consideration, as well as add face matching in Phase 2.
