import os, sys
import shutil
import maya.cmds as cmds
import maya.mel as mel

import tank
from tank import Hook
from tank import TankError

## Now get the custom tools
if 'T:/software/lsapipeline/custom' not in sys.path:
    sys.path.append('T:/software/lsapipeline/custom')
from debug import debug
import utils as utils
import shader_lib as shd
#reload(shd)


class PublishHook(Hook):
    """
    Single hook that implements publish functionality for secondary tasks
    """    
    def execute(self, tasks, work_template, comment, thumbnail_path, sg_task, primary_publish_path, progress_cb, **kwargs):
        """
        Main hook entry point
        :tasks:         List of secondary tasks to be published.  Each task is a 
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

        :comment:       String
                        The comment provided for the publish

        :thumbnail:     Path string
                        The default thumbnail provided for the publish

        :sg_task:       Dictionary (shotgun entity description)
                        The shotgun task to use for the publish    

        :primary_publish_path: Path string
                        This is the path of the primary published file as returned
                        by the primary publish hook

        :progress_cb:   Function
                        A progress callback to log progress during pre-publish.  Call:

                            progress_cb(percentage, msg)

                        to report progress to the UI

        :returns:       A list of any tasks that had problems that need to be reported 
                        in the UI.  Each item in the list should be a dictionary containing 
                        the following keys:
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
        ## Make sure the scene assembly plugins are loaded
        utils.loadSceneAssemblyPlugins(TankError)
            
        results = []
        assemblyDefinitionPublishPath = ''
        ## Do a pass and get the assembly definition path now before anything else is done.
        for task in tasks:
            item = task["item"]
            output = task["output"]
            if output["name"] == 'assembly_definition':
                assemblyDefinitionPublishPath = self._getAssemblyDefinitionPath(item, output, work_template)
            else:
                pass

        ## PROCESS THE REPRESENTATION FILES FIRST                
        for task in tasks:
            item = task["item"]
            output = task["output"]
            errors = []

            # report progress:
            progress_cb(0, "Publishing", task)

            # DO EVERYTHING EXCEPT THE ASSEMBLY DEF WHICH REQUIRES ALL OF THESE TO BE EXPORTED
            if output["name"] == "alembic_cache":
                try:
                    self._publish_alembic_cache_for_item(item, output, work_template, assemblyDefinitionPublishPath, sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                    errors.append("Publish failed - %s" % e)
                    
            elif output["name"] == 'bounding_box':
                try:
                    self._publish_bbox_for_item(item, output, work_template, assemblyDefinitionPublishPath, sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                    errors.append("Publish failed - %s" % e)
           
            elif output["name"] == 'gpu_cache':
                try:
                    self._publish_gpu_for_item(item, output, work_template, assemblyDefinitionPublishPath, sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                    errors.append("Publish failed - %s" % e)
                    
            elif output["name"] == 'assembly_definition':
                pass
            
            elif output["name"] == 'shader_export':
                pass
            
            else:
                # don't know how to publish this output types!
                errors.append("Don't know how to publish this item!")
        progress_cb(100)
       
        ## NOW DO THE ASSEMBLY DEFINITON AND PUBLISH THIS WITH THE MAYA WORKING FILE AS A DEP
        for task in tasks:
            item = task["item"]
            output = task["output"]
            errors = []
            # report progress:
            progress_cb(0, "Publishing", task)
            # publish alembic_cache output
            if output["name"] == 'assembly_definition':
                try:
                    self._publish_assemblyDefinition_for_item(tasks, item, output, work_template, primary_publish_path, sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                    errors.append("Publish failed - %s" % e)           
            else:
                pass

        ## NOW PUBLISH THE REPRESENTATIONS WITH THE SCENE ASSEMBLY DEF PATH AS A DEP
        ## This is done here to make sure the deps get logged properly
        for task in tasks:
            item = task["item"]
            output = task["output"]
            errors = []
            # report progress:
            progress_cb(0, "Publishing", task)
            # publish alembic_cache output
            if output["name"] == 'alembic_cache':
                try:
                    type = 'ABC'
                    self._doRepresentationPublish(type, item, output, work_template, assemblyDefinitionPublishPath, sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                    errors.append("Publish failed - %s" % e)
            elif output["name"] == 'gpu_cache':
                try:
                    type = 'GPU'
                    self._doRepresentationPublish(type, item, output, work_template, assemblyDefinitionPublishPath, sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                    errors.append("Publish failed - %s" % e)         
            if output["name"] == 'bounding_box':
                try:
                    type = 'BBOX'
                    self._doRepresentationPublish(type, item, output, work_template, assemblyDefinitionPublishPath, sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                    errors.append("Publish failed - %s" % e)     
            else:
                pass

            ## if there is anything to report then add to result
            if len(errors) > 0:
                ## add result:
                results.append({"task":task, "errors":errors})
            progress_cb(100)
        return results

    def _publish_alembic_cache_for_item(self, item, output, work_template, primary_publish_path, sg_task, comment, thumbnail_path, progress_cb):
        """
        Export an Alembic cache for the specified item and publish it
        to Shotgun.
        """
        group_name = item["name"].strip("|")
        tank_type = output["tank_type"]
        publish_template = output["publish_template"]

        # get the current scene path and extract fields from it
        # using the work template:
        scene_path = os.path.abspath(cmds.file(query=True, sn= True))
        fields = work_template.get_fields(scene_path)
        publish_version = fields["version"]

        # update fields with the group name:
        fields["grp_name"] = group_name

        ## create the publish path by applying the fields 
        ## with the publish template:
        publish_path = publish_template.apply_fields(fields)

        ## Now scan the geo in the scene and preserve the crease information
        meshes = cmds.ls(type = 'mesh', l = True)
        [( cmds.addAttr('%s' % mesh, ln = 'SubDivisionMesh', at = 'bool'), cmds.setAttr('%s.SubDivisionMesh' % mesh, 1) ) for mesh in meshes if not cmds.objExists('%s.SubDivisionMesh' % mesh)]

        ## build and execute the Alembic export command for this item:
        frame_start = 1
        frame_end = 1
        abc_export_cmd = "-attr SubDivisionMesh -attr smoothed -attr dupAsset -attr mcAssArchive -attr version -uvWrite -wholeFrameGeo -worldSpace -fr %d %d -root %s -file %s" % (frame_start, frame_end, item["name"], publish_path)
        try:
            self.parent.log_debug("Executing command: %s" % abc_export_cmd)
            print '====================='
            print 'Exporting alembic now to %s' % publish_path
            cmds.AbcExport(verbose = True, j = abc_export_cmd)
            print 'Finished alembic export...'
            print '====================='
        except Exception, e:
            raise TankError("Failed to export Alembic Cache")

    def _publish_bbox_for_item(self, item, output, work_template, primary_publish_path, sg_task, comment, thumbnail_path, progress_cb):
        """
        Export a bounding box for the specified item and publish it  to Shotgun.
        """
        group_name = item["name"].strip("|")
        tank_type = output["tank_type"]
        publish_template = output["publish_template"]        
                
        # get the current scene path and extract fields from it using the work template:
        scene_path = os.path.abspath(cmds.file(query=True, sn= True))
        fields = work_template.get_fields(scene_path)
        publish_version = fields["version"]

        # update fields with the group name:
        fields["grp_name"] = group_name

        ## create the publish path by applying the fields with the publish template:
        publish_path = publish_template.apply_fields(fields)
        bboxName = '%s' %  group_name.split('_hrc')[0] 
        ## CHECK FOR BOUNDING BOX OBJECT
        if not cmds.objExists(bboxName):
            print 'Could not find bounding box mesh. Trying to make one now'
            ## build and execute the bbox now...
            boundingBoxes = []
            for eachChild in cmds.listRelatives(group_name, children = True):
                if not 'placements' in eachChild:
                    boundingBoxes.append(eachChild)
            cmds.geomToBBox(boundingBoxes, name = bboxName, combineMesh=True, keepOriginal=True,  nameSuffix='_bbox', shaderColor=[1.0, 1.0, 0.0])
       
        try:
            self.parent.log_debug("Executing bbox export now to: \n\t\t%s" % publish_path)
            print '====================='
            print 'Exporting bbox now to %s' % publish_path
            #PUT THE FILE EXPORT COMMAND HERE
            cmds.select('%s_bbox' % bboxName, r = True)
            cmds.file(publish_path, options = "v=0;", typ = "mayaBinary", es = True , force = True)
            cmds.delete('%s_bbox' % bboxName)
            print 'Finished bbox export...'
            print '====================='
        except Exception, e:
            raise TankError("Failed to export boundingBox")

    def _publish_gpu_for_item(self, item, output, work_template, primary_publish_path, sg_task, comment, thumbnail_path, progress_cb):
        """
        Export a gpu cache for the specified item and publish it  to Shotgun.
        """
        group_name = item["name"].strip("|")
        debug(app = None, method = '_publish_gpu_for_item', message = 'group_name: %s' % group_name, verbose = False)
        tank_type = output["tank_type"]
        publish_template = output["publish_template"]        
                
        # get the current scene path and extract fields from it using the work template:
        scene_path = os.path.abspath(cmds.file(query=True, sn= True))
        fields = work_template.get_fields(scene_path)
        publish_version = fields["version"]

        # update fields with the group name:
        fields["grp_name"] = group_name

        ## create the publish path by applying the fields with the publish template:
        publish_path = publish_template.apply_fields(fields)
        #'@asset_root/publish/gpu/{name}[_{grp_name}].v{version}.abc'
        gpuFileName = os.path.splitext(publish_path)[0].split('\\')[-1] 
        fileDir = '/'.join(publish_path.split('\\')[0:-1])
        debug(app = None, method = '_publish_gpu_for_item', message = 'gpuFileName: %s' % gpuFileName, verbose = False)
        
        ## Now fix the shaders
        shd.fixDGForGPU()
        
        if cmds.objExists('CORE_ARCHIVES_hrc'):
            cmds.setAttr('CORE_ARCHIVES_hrc.visiblity', 0)
        
        if cmds.objExists('ROOT_ARCHIVES_DNT_hrc'):
            cmds.setAttr('ROOT_ARCHIVES_DNT_hrc.visiblity', 0)
                                       
        ## build and execute the gpu cache export command for this item:
        try:
            print '====================='
            print 'Exporting gpu now to %s\%s' % (fileDir, gpuFileName)
            #PUT THE FILE EXPORT COMMAND HERE
            cmds.select(clear = True)
            for geo in cmds.listRelatives(group_name, children = True):
                if 'geo_hrc' in geo:
                    geoGroup = str(group_name)
                    debug(app = None, method = '_publish_gpu_for_item', message = 'geoGroup: %s' % geoGroup, verbose = False)
                
            cmds.select(geoGroup)
            
            debug(app = None, method = '_publish_gpu_for_item', message = 'geoGroup: %s' % geoGroup, verbose = False)
            debug(app = None, method = '_publish_gpu_for_item', message = "gpuCache -startTime 1 -endTime 1 -optimize -optimizationThreshold 40000 -directory \"%s\" -fileName %s %s;" % (fileDir, gpuFileName, geoGroup), verbose = False)
            
            mel.eval("gpuCache -startTime 1 -endTime 1 -optimize -optimizationThreshold 40000 -directory \"%s\" -fileName %s %s;" % (fileDir, gpuFileName, geoGroup))

            print 'Finished gpu export...'
            print '====================='
            
            if cmds.objExists('dgSHD'):            
                ## Now reconnect the FileIn nodes
                for key, var in filesDict.items():
                    cmds.connectAttr('%s.outColor' % key, '%s.color' % var)
        except Exception, e:
            raise TankError("Failed to export gpu cache file")

    def _doRepresentationPublish(self, type, item, output, work_template, primary_publish_path, sg_task, comment, thumbnail_path, progress_cb):
        group_name = '%s%s' % (''.join(item["name"].strip("|").split('_hrc')[0].split('_')), type)
        tank_type = output["tank_type"]
        publish_template = output["publish_template"]  
        
        # get the current scene path and extract fields from it
        # using the work template:
        scene_path = os.path.abspath(cmds.file(query=True, sn= True))
        fields = work_template.get_fields(scene_path)
        publish_version = fields["version"]       
        # update fields with the group name:
        fields["grp_name"] = group_name
        ## create the publish path by applying the fields with the publish template:
        publish_path = publish_template.apply_fields(fields)
        print '====================='
        print 'Publishing to %s' % publish_path
    
        self._register_publish(publish_path, 
                              group_name, 
                              sg_task, 
                              publish_version, 
                              tank_type,
                              comment,
                              thumbnail_path, 
                              [primary_publish_path])       
        
    def _getAssemblyDefinitionPath(self, item, output, work_template):
        """
        Get the output path for the assembly definition file so that the publishes for the 2ndry outputs publish with this as their dep and not the primary publish path.
        """
        group_name = item["name"].strip("|")
        tank_type = output["tank_type"]
        publish_template = output["publish_template"]        
        # get the current scene path and extract fields from it
        # using the work template:
        scene_path = os.path.abspath(cmds.file(query=True, sn= True))
        fields = work_template.get_fields(scene_path)
        publish_version = fields["version"]
        # update fields with the group name:
        fields["grp_name"] = group_name
        ## create the publish path by applying the fields 
        ## with the publish template:
        publish_path = publish_template.apply_fields(fields)

        return publish_path
        
    def _publish_assemblyDefinition_for_item(self, mytasks, item, output, work_template, primary_publish_path, sg_task, comment, thumbnail_path, progress_cb):
        """
        Export a gpu cache for the specified item and publish it  to Shotgun.
        """
        group_name = item["name"].strip("|")
        tank_type = output["tank_type"]
        publish_template = output["publish_template"]        
        # get the current scene path and extract fields from it
        # using the work template:
        scene_path = os.path.abspath(cmds.file(query=True, sn= True))
        fields = work_template.get_fields(scene_path)
        publish_version = fields["version"]
        # update fields with the group name:
        fields["grp_name"] = group_name
        ## create the publish path by applying the fields 
        ## with the publish template:
        publish_path = publish_template.apply_fields(fields)
      
        ## GET THE PREVIOUS SECONDARY PATHS NOW
        myAlembicFilePath = ''
        myBoundingBoxSceneFilePath = ''
        myGPUFilePath = ''
        myMayaScenePath = primary_publish_path.replace('\\', '/')
        
        ## Now fetch these paths by processing each secondary outputs publishPath again
        for eachSecondary in mytasks:
            sec_item = eachSecondary["item"]
            sec_output = eachSecondary["output"]
            sec_group_name = sec_item["name"].strip("|")
            sec_tank_type = sec_output["tank_type"]
            sec_publish_template = sec_output["publish_template"]        
            # get the current scene path and extract fields from it
            # using the work template:
            sec_scene_path = os.path.abspath(cmds.file(query=True, sn= True))
            sec_fields = work_template.get_fields(sec_scene_path)
            sec_publish_version = sec_fields["version"]
            # update fields with the group name:
            sec_fields["grp_name"] = group_name
            ## create the publish path by applying the fields 
            ## with the publish template:
            sec_publish_path = sec_publish_template.apply_fields(sec_fields)
            if sec_output["name"] == "alembic_cache":
                myAlembicFilePath = (sec_publish_path).replace('\\', '/')
            elif sec_output["name"] == 'bounding_box':
                myBoundingBoxSceneFilePath = (sec_publish_path).replace('\\', '/')
            elif sec_output["name"] == 'gpu_cache':
                myGPUFilePath = (sec_publish_path).replace('\\', '/')
            else:
                pass
        
#         print  myAlembicFilePath
#         print  myBoundingBoxSceneFilePath
#         print  myGPUFilePath
#         print myMayaScenePath
        ## build and execute the assembly definition export command for this item:
        try:
            self.parent.log_debug("Executing scene assembly export now to: \n\t\t%s" % publish_path)
            print '====================='
            print 'Publishing scene assembly now to %s' % publish_path
            try:
                assemblyName =  '%s_ADEF'  % group_name.split('_hrc')[0]
                cmds.assembly(n = assemblyName)
                print 'AssemblyDef created: \t %s' % assemblyName
            except:
                raise TankError("Scene Assembly plugin not loaded!!")
            
            #cmds.assembly(assemblyName, edit = True, createRepresentation = 'Locator') ## No point, as we're modeling to world positions.
            cmds.assembly(assemblyName, edit = True, input = myGPUFilePath, createRepresentation = 'Cache')
            cmds.assembly(assemblyName, edit = True, input = myAlembicFilePath, createRepresentation = 'Cache')
            cmds.assembly(assemblyName, edit = True, input = myBoundingBoxSceneFilePath, createRepresentation = 'Scene')
            cmds.assembly(assemblyName, edit = True, input = myMayaScenePath, createRepresentation = 'Scene')
            myRepresentations = cmds.assembly(assemblyName, query = True, listRepresentations = True)
            print 'Added Representations: \t%s' % myRepresentations
            for x in range(0, len(myRepresentations)):
                getRepName = cmds.getAttr("%s.representations[%s].repName" % (assemblyName, x))
                getRepData = cmds.getAttr("%s.representations[%s].repData" % (assemblyName, x))
                getRepLabel = cmds.getAttr("%s.representations[%s].repLabel" % (assemblyName, x))
                getRepType = cmds.getAttr("%s.representations[%s].repType"  % (assemblyName, x))
                if 'alembic' in getRepData:
                    cmds.setAttr("%s.representations[%s].repLabel" % (assemblyName, x), 'alembicCache', type = 'string')
                    cmds.setAttr("%s.representations[%s].repName" % (assemblyName, x), 'alembicCache', type = 'string')
                elif 'gpu' in getRepData:
                    cmds.setAttr("%s.representations[%s].repLabel" % (assemblyName, x), 'gpuCache', type = 'string')
                    cmds.setAttr("%s.representations[%s].repName" % (assemblyName, x), 'gpuCache', type = 'string')
                elif 'bbox' in getRepData:
                    cmds.setAttr("%s.representations[%s].repLabel" % (assemblyName, x), 'bbox', type = 'string')
                    cmds.setAttr("%s.representations[%s].repName" % (assemblyName, x), 'bbox', type = 'string')
                elif 'maya' in getRepData:
                    cmds.setAttr("%s.representations[%s].repLabel" % (assemblyName, x), 'full', type = 'string')
                    cmds.setAttr("%s.representations[%s].repName" % (assemblyName, x), 'full', type = 'string')
#                 if 'Locator' in getRepType:
#                     cmds.setAttr("%s.representations[%s].repLabel" % (assemblyName, x), 'locator', type = 'string')
            print 'Done setting representation labels.'
            cmds.assembly(assemblyName, edit = True, active = 'gpuCache')
            print 'Done setting active to gpuCache.'
            ##Now set the auxNodes to something that won't clash during a shot build!!
            bad = ['hyperLayout', 'hyperGraphInfo', 'hyperView']
            for each in bad:
                print "CHECKING FOR ASSEMBLY DEFINITION HYPERLAYOUTS NOW"
                for eachNaughty in cmds.ls(type = each):
                    try:
                        getAdef = cmds.listConnections(eachNaughty)
                        if getAdef:
                            if '_ADEF' in getAdef[0]:
                                print 'Renamed %s to %s' % (eachNaughty, '%s_%s' % (getAdef[0], each))
                                cmds.rename(eachNaughty, '%s_%s' % (getAdef[0], each))
                    except TypeError:
                        pass
            ## Now do the export
            cmds.select(assemblyName, r = True)
            print 'Exporting sceneAssemblyDefinition: \t %s' % publish_path
            cmds.file(publish_path, options = "v=0;", typ = "mayaAscii", es = True , force = True)
            cmds.delete(assemblyName)            
            print 'Finished scene assembly publish...'
            print '====================='
        except Exception, e:
             raise TankError("Failed to export scene assembly definition %s" % e) 

        ## Finally, register this publish with Shotgun
        self._register_publish(publish_path, 
                               '%sADEF' % ''.join(group_name.split('_hrc')[0].split('_')), 
                               sg_task, 
                               publish_version, 
                               tank_type,
                               comment,
                               thumbnail_path,
                               [primary_publish_path])

    def _register_publish(self, path, name, sg_task, publish_version, tank_type, comment, thumbnail_path, dependency_paths=None):
        """
        Helper method to register publish using the 
        specified publish info.
        """
        # construct args:
        args = {
            "tk": self.parent.tank,
            "context": self.parent.context,
            "comment": comment,
            "path": path,
            "name": name,
            "version_number": publish_version,
            "thumbnail_path": thumbnail_path,
            "task": sg_task,
            "dependency_paths": dependency_paths,
            "published_file_type":tank_type,
        }

        # register publish;
        sg_data = tank.util.register_publish(**args)
        if dependency_paths:
            print "================DEP===================="
            print '%s dependencies: \n\t%s' % (path, dependency_paths[0])
            print "========================================"
        return sg_data