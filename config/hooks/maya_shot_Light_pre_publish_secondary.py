# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os, sys
import maya.cmds as cmds
if 'T:/software/lsapipeline/custom' not in sys.path:
    sys.path.append('T:/software/lsapipeline/custom')
from debug import debug
import tank
from tank import Hook
from tank import TankError

class PrePublishHook(Hook):
    """
    Single hook that implements pre-publish functionality
    """
    def execute(self, tasks, work_template, progress_cb, **kwargs):
        """
        Main hook entry point
        :tasks:         List of tasks to be pre-published.  Each task is be a 
                        dictionary containing the following keys:
                        {   
                            item:   Dictionary
                                    This is the item returned by the scan hook 
                                    {   
                                        name:           String
                                        description:    String
                                        type:           String
                                        other_params:   Dictionary
                                    }
                                   
                            output: Dictionary
                                    This is the output as defined in the configuration - the 
                                    primary output will always be named 'primary' 
                                    {
                                        name:             String
                                        publish_template: template
                                        tank_type:        String
                                    }
                        }
                        
        :work_template: template
                        This is the template defined in the config that
                        represents the current work file
               
        :progress_cb:   Function
                        A progress callback to log progress during pre-publish.  Call:
                        
                            progress_cb(percentage, msg)
                             
                        to report progress to the UI
                        
        :returns:       A list of any tasks that were found which have problems that
                        need to be reported in the UI.  Each item in the list should
                        be a dictionary containing the following keys:
                        {
                            task:   Dictionary
                                    This is the task that was passed into the hook and
                                    should not be modified
                                    {
                                        item:...
                                        output:...
                                    }
                                    
                            errors: List
                                    A list of error messages (strings) to report    
                        }
        """       
        results = []

        ## Get rid of stupid empty reference nodes...
        [(cmds.lockNode(ref, lock = False), cmds.delete(ref)) for ref in cmds.ls(type = 'reference')]
        
        # validate tasks:
        for task in tasks:
            debug(app = None, method = 'lighingPrePublish.execute', message = 'task: %s' % task, verbose = False)
            item = task["item"]
            debug(app = None, method = 'lighingPrePublish.execute', message = 'item: %s' % item, verbose = False)
            output = task["output"]
            errors = []
            # report progress:
            progress_cb(0, "Validating", task)
            if item["type"] == "light_grp":
                errors.extend(self._validate_item_for_publish(item))
                debug(app = None, method = 'lighingPrePublish.execute', message = 'light_grp validated', verbose = False)
            elif item["type"] == "cam_grp":
                errors.extend(self._validate_item_for_publish(item))
                debug(app = None, method = 'lighingPrePublish.execute', message = 'cam_grp validated', verbose = False)
            elif item["type"] == "mesh_grp":
                errors.extend(self._validate_item_for_publish(item))
                debug(app = None, method = 'lighingPrePublish.execute', message = 'mesh_grp validated', verbose = False)
            elif item["type"] == "fx_grp":
                errors.extend(self._validate_item_for_publish(item))
                debug(app = None, method = 'lighingPrePublish.execute', message = 'fx_grp validated', verbose = False)
            # elif item["type"] == "renderPreview":
            #     debug(app = None, method = 'lighingPrePublish.execute', message = 'renderPreview validated', verbose = False)
            #     pass
            elif item["type"] == "renderFinal":
                debug(app = None, method = 'lighingPrePublish.execute', message = 'renderFinal validated', verbose = False)
                pass
            elif item["type"] == "xml_grp":
                debug(app = None, method = 'lighingPrePublish.execute', message = 'xml_grp validated', verbose = False)
                pass
            else:
                # don't know how to publish this output types!
                errors.append("Don't know how to publish this item! \nPlease contact your supervisor..." % output["name"])
            # if there is anything to report then add to result
            if len(errors) > 0:
                # add result:
                results.append({"task":task, "errors":errors})
                
            progress_cb(100)
                
        debug(app = None, method = 'lighingPrePublish.execute', message = 'Returning Results....', verbose = False)
        return results

    def _validate_item_for_publish(self, item):
        """
        Validate that the item is valid to be exported 
        to an alembic cache
        """
        errors = []
        ## FINAL CHECKS PRE PUBLISH JUST TO MAKE SURE NOTHING ODD HAS HAPPENED IN THE SCENE BEFORE CLICKING THE PUBLISH BUTTON
        # check that the group still exists:
        try:
            [cam for cam in cmds.ls(type = 'camera')  if 'shotCam_bake' in cam][0].replace('Shape', '')
        except:
            errors.append("ShotCamera couldn't be found in the scene!")
        if not cmds.objExists(item["name"]):
            errors.append("%s couldn't be found in the scene!" % item["name"])
        # finally return any errors
        return errors