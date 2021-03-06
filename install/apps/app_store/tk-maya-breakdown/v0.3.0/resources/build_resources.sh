#!/usr/bin/env bash
# 
# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

echo "building user interfaces..."
pyside-uic --from-imports dialog.ui > ../python/tk_maya_breakdown/ui/dialog.py
pyside-uic --from-imports item.ui > ../python/tk_maya_breakdown/ui/item.py

echo "building resources..."
pyside-rcc resources.qrc > ../python/tk_maya_breakdown/ui/resources_rc.py
