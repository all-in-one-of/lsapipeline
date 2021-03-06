# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook that loads items into the current scene. 

This hook supports a number of different platforms and the behaviour on each platform is
different. See code comments for details.


"""
import tank
import os

class AddFileToScene(tank.Hook):
    
    def execute(self, engine_name, file_path, shotgun_data, **kwargs):
        """
        Hook entry point and app-specific code dispatcher
        """
                
        if engine_name == "tk-maya":
            self.add_file_to_maya(file_path, shotgun_data)

        else:
            raise Exception("Don't know how to load file into unknown engine %s" % engine_name)
        
    ###############################################################################################
    # app specific implementations
    
    def add_file_to_maya(self, file_path, shotgun_data):
        """
        Load file into Maya.
        
        This implementation creates a standard maya reference file for any item.
        """
        
        import pymel.core as pm
        import maya.cmds as cmds
        
        # get the slashes right
        file_path = file_path.replace(os.path.sep, "/")
        
        (path, ext) = os.path.splitext(file_path)
              
        if ext in [".ma", ".mb"]:
            # maya file - load it as a reference
            getEntity = shotgun_data['entity']
            namespace = getEntity['name']
            if not cmds.objExists(namespace):
                cmds.file(file_path, i = True, f = True)
                ## Clean out any imported namespaces
                for eachNode in cmds.ls(ap= True):
                    if ':' in eachNode:
                        try:
                            cmds.rename(eachNode, '%s' % eachNode.split(':')[-1])
                        except RuntimeError:
                            pass
            else:
                cmds.warning('Audio already exists in the scene. Use the scene breakdown to update your audio.')
            

        else:
            self.parent.log_error("Unsupported file extension for %s! Nothing will be loaded." % file_path)
