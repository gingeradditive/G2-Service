#!/bin/bash

# Banner
RED='\033[0;31m'
NC='\033[0m'
echo "${RED}                                                        
                 5@?                                                            
    :~!7!~:  :^. ~!^ .^^  ^!77!:        .^!77!^  :^:     :~!77!^.    ^^..!7~.   
 .?B&#GPPG#BJB@7 P@J 7@#JBBPPPB&G!    !G&#GPPGB#YP@5   7B&BGPPB##5^  #@B#BGY    
~#@5^     .!B@@7 P@J 7@@#!.    !@@~ :G@G~.    .~P@@5 :B@5:     .!#@? #@@!       
&@J         .#@7 P@J 7@&:       P@Y 5@P          P@5 G@&YJYYYYYJJP@@~B@Y        
@@!          B@7 P@J 7@#        5@5 P@Y          5@5 #@P7????????777^B@7        
7@&7       :P@@7 P@J 7@#        5@5 ^&@J.      .J@@5 ?@#:        !5~ #@7     :: 
 ^5&#PYJY5G#P#@7 G@J ?@#.       5@5  .J##G5JJ5G#GB@5  7#@P7~^^!JB@P^ #@?    G@@G
^~:.~7JJJ?~.:&@^ ?P! ~PY        7P7 :~^.^7JJJ?!. B@7    !YGGBBGP?^   YP~    ?GG?
~B@P!:. ..^J&&7                     :P@G7:.  .^7B@Y                             
  !P#######GJ:                        ~5B######BY^                              ${NC}"
echo
echo "G2-Service"
echo "Version 0.0.1 - By: Giacomo Guaresi"
echo; echo


SYMBOLIC_LINK_DESTINATION="$HOME/printer_data/config/G2-Service"
G2_SERVICE_DIR="$HOME/G2-Service/Configs"
G2_DATABASE_DIR="$HOME/G2-Service/Database"
G2_GCODES_DIR="$HOME/G2-Service/Gcodes"

# Copy the files
echo "Copying G2-Service to printer_data/config"
if [ -d "$G2_SERVICE_DIR" ]; then
    cp -r "$G2_SERVICE_DIR"/* "$HOME/printer_data/config/"
    echo "G2-Service copied to printer_data/config"
else
    echo "G2-Service directory does not exist."
    exit 1
fi

# Remove the existing G2-Service folder or link if it exists
if [ -e "$SYMBOLIC_LINK_DESTINATION" ]; then
    sudo rm -rf "$SYMBOLIC_LINK_DESTINATION"
    echo "Existing G2-Service removed"
fi

# Create the symbolic link
sudo ln -s "$HOME/G2-Service/Configs" "$SYMBOLIC_LINK_DESTINATION"
sudo chown -h pi:pi "$SYMBOLIC_LINK_DESTINATION"
echo "Symbolic link created for Ginger Configs"

echo "Install mainsail style"
mkdir /home/pi/printer_data/config/.theme
ln -sf $HOME/G2-Service/Styles/mainsail-ginger/*.* "/home/pi/printer_data/config/.theme/"

# echo "Activate light mode default"
# sed -i 's/"defaultMode": "dark"/"defaultMode": "light"/' /home/pi/mainsail/config.json


echo "Restoring Moonraker DB..."
mkdir "$HOME/printer_data/database/"
cp -f "$G2_DATABASE_DIR"/moonraker-sql.db "$HOME/printer_data/database/"

echo "Copy factory gcodes..."
mkdir -p "$HOME/printer_data/gcodes/"
cp -rf "$G2_GCODES_DIR"/* "$HOME/printer_data/gcodes/"