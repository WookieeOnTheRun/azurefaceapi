# azurefaceapi
Using Azure Cognitive Services Face API to detect faces ( Phase 1 ) and match faces ( Phase 2 )

The script currently connects to an Azure Blob Storage Account and loops through supported image files to detect faces ( metadata extraction has been removed due to future removal by MSFT ). 

Similarity will be checked across image(s) currently being processed; if any is detected verification will take place against any faces that are current in existing FaceGroups. Based on findings, new image(s) will either be added to existing PersonGroup(s) or added to a new PersonGroup.
