# Video conferencing page

Uses PeerJS to wire together some webcams.




# Development setup

## Database and configuration initialization
`make initialize`

Creates instance/gotchufam.ini and instance/app.db

DO NOT RUN IN PRODUCTION.

## Create a family
`FLASK_APP=gotchufam.app flask add-family 'Test Family'`

## Show families
`FLASK_APP=gotchufam.app flask list-families`

