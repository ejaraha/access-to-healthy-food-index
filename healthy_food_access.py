# -*- coding: utf-8 -*-
"""
Created on Sun Apr 21 15:31:25 2019

@author: sjara
"""
from __future__ import absolute_import, division, print_function

import arcpy, os, urllib2, zipfile

# set working directory
arcpy.env.workspace = 'ENTER WORKING DIRECTORY'
workspace = arcpy.env.workspace
arcpy.env.overwriteOutput = True

# DEFINE FUNCIONS FOR DOWNLOADING FILES

def fetch_zip(url, destination):
    '''fetch and save binary web content
    # url (str): url to binary web content
    # destination (str): location to save binary web content'''
    response = urllib2.urlopen(url)
    bin_contents = response.read()
    response.close()
    out_file_name = os.path.join(destination, os.path.basename(url))
    with open(out_file_name, 'wb') as outf:
        outf.write(bin_contents)
    
def unzip_archive(archive, destination):
    '''Extract files
    # archive_name (str): name of zipped folder
    # destination (str): location to save extracted files'''
    print('Unzip {0} to {1}'.format(archive, destination))
    # get a zipfile object
    with zipfile.ZipFile(archive, 'r') as zip_obj:
        zip_obj.extractall(destination)
        # report the list of files extracted from the archive
        archive_list = zip_obj.namelist()
        for file_name in archive_list:
            print('Extract file: {0}...'.format(file_name))
    print('Extraction complete')

def philadelphia_healthy_food_access_get_data(destination):
    '''fetch, extract, and save binary web content
    # zip_urls (list of str): urls to binary web content
    # destination (str): directory to output zipped and unzipped files'''
    # define paths to files for analysis:
    ## philly neighborhoods, walkable access to health food, dvprc land use, farmers market locations, WIC locations
    zip_urls = ['https://github.com/azavea/geo-data/raw/master/Neighborhoods_Philadelphia/Neighborhoods_Philadelphia.zip'\
                ,'http://data.phl.opendata.arcgis.com/datasets/4748c96b9db444a48de1ae38ca93f554_0.zip'\
                ,'http://dvrpc.dvrpcgis.opendata.arcgis.com/datasets/c614fd0ae78a4aeaad319ad2e1007cbf_0.zip'\
                ,'http://data.phl.opendata.arcgis.com/datasets/0707c1f31e2446e881d680b0a5ee54bc_0.zip'\
                ,'http://data.phl.opendata.arcgis.com/datasets/2458f233003e4d57be1aeff41abb0121_0.zip']
    # fetch and unzip files
    for url in zip_urls:
        fetch_zip(url, destination)
        print('{0}{1} created.'.format(destination,os.path.basename(url)))
        archive = os.path.join(destination, os.path.basename(url))
        if not os.path.exists(destination):
            os.makedirs(destination)
        unzip_archive(archive, destination)

# DEFINE FUNCTIONS FOR ANALYSIS

def wgs_to_nad1983(feature_classes, destination):
    '''Transform feature class(es) from  WGS 1984
    to NAD 1983 StatePlane PA South FIPS 3702 Feet.
    # feature_classes (list of str): feature classes to transform
    # destination (str): directory to output transformed feature classes'''
    for fc in feature_classes:
            outpt = os.path.splitext(fc)[0].lower()+'_nad_1983.shp'
            coord_sys_out = arcpy.SpatialReference(2272) # NAD 1983 StatePlane Pennsylvania South FIPS 3702 Feet
            transformation = 'WGS_1984_(ITRF00)_To_NAD_1983'
            print('transforming {} from WGS 1984 to NAD 1983 StatePlane PA South FIPS 3702 Feet'.format(fc))
            arcpy.Project_management(fc,outpt,coord_sys_out,transformation)
            print('transformation complete: {}'.format(outpt))

def philadelphia_healthy_food_access_analysis(destination):
    '''Analyses downloaded with the philadelphia_healthy_food_access_get_data() function 
    1) identify philadelphia neighborhoods with >= 40 % residential land use
    2) calculate walkable food access score for neighborhoods with >= 40% residential land use
    '''
    
    # transform geographic coordinates 
    transform_list = ['DVRPC_2010_Land_Use_Feature_Service.shp','Walkable_Access_Healthy_Food.shp','Farmers_Markets.shp','WIC_Offices.shp']
    wgs_to_nad1983(transform_list, destination)
    
    # assign shapefiles to variables
    land_use = 'dvrpc_2010_land_use_feature_service_nad_1983.shp'
    neighborhoods = 'Neighborhoods_Philadelphia.shp'
    food_access = 'walkable_access_healthy_food_nad_1983.shp'
    wic = 'WIC_Offices.shp'
    farmers_markets = 'Farmers_Markets.shp'
    
    # select records with residential land use from dvrpc_2010_land_use_feature_service_nad_1983.shp
    land_use_fl = arcpy.MakeFeatureLayer_management(land_use,'land_use_fl')
    in_layer = land_use_fl
    out_class = 'land_use_res.shp'
    where = '"LU_5CAT"=\'Residential\''
    print('selecting residential parcels from {}: {}'.format(land_use,out_class))
    land_use_res = arcpy.Select_analysis(in_layer,out_class,where)
    print('selection complete')
    land_use_res = out_class
    
    # clip neighborhoods using land_use_res.shp --> residential.shp
    neighborhoods_fl = arcpy.MakeFeatureLayer_management(neighborhoods,'neighborhoods_fl')
    land_use_res_fl = arcpy.MakeFeatureLayer_management(land_use_res,'land_use_res_fl')
    in_layer = neighborhoods_fl
    clip_layer = land_use_res_fl
    out_class = 'residential.shp'
    print('clipping {} using {}: {}'.format(in_layer,clip_layer,out_class))    
    arcpy.Clip_analysis(in_layer,clip_layer,out_class)
    print('clip complete')
    residential = out_class
    
    # add geometry attributes for residential.shp
    print("adding geometry attributes to {}".format(residential))
    residential_fl = arcpy.MakeFeatureLayer_management(residential,'residential_fl')
    arcpy.AddGeometryAttributes_management(residential_fl,'AREA')
    print("done")
    
    # calculate percent area per neighborhood that is residential: pct_res
    new_field = 'pct_res'
    print("adding a field to {}: {}".format(residential,new_field))
    arcpy.AddField_management(residential,new_field,'Double')
    calc = '!POLY_AREA!/!Shape_Area!*100'
    print("updating {} as {}".format(new_field, calc))
    arcpy.CalculateField_management(residential,new_field,calc,"PYTHON_9.3","") 
    print("done")
    
    # join pct_res field to neighborhoods.shp 
    in_data = neighborhoods_fl
    join_data = residential_fl
    join_field = 'NAME'
    fields = 'pct_res'
    print("joining {} field from {} to {}".format(fields,residential,neighborhoods))
    print("join field: {}".format(join_field))
    arcpy.JoinField_management(in_data,join_field,join_data,join_field,fields)
    print("join complete")
    
    # select neighborhoods that are > 40% residential --> neighborhoods_gt40pct_res.shp
    in_layer = neighborhoods_fl
    out_class = 'neighborhoods_gt40pct_res.shp'
    where = '"pct_res">=40'
    print('selecting residential parcels from {}: {}'.format(in_layer,out_class))
    land_use_res = arcpy.Select_analysis(in_layer,out_class,where)
    print('select complete')
    neigh_gt40pct_res = out_class
    
    # assign scores corresponding to access classifications : access_num
    new_field = 'access_num'
    codeblock = """def access_num(text):
        if text == 'High Access':
            return 0.03
        elif text == 'Moderate Access':
            return 0.02
        elif text == 'Low Access':
            return 0.01
        elif text == 'No Access':
            return 0.00
    """
    print("adding a field to {}: {}".format(food_access,new_field))
    arcpy.AddField_management(food_access,new_field,'DOUBLE')
    calc = 'access_num(!ACCESS_!)'
    print("updating {} with numeric access scores".format(new_field))
    arcpy.CalculateField_management(food_access,new_field,calc,"PYTHON_9.3",codeblock) 
    print("done")
    
    # intersect food_access and access_gt40pct_res to get correct boundaries --> access_gt40pct_res_intersect.shp
    food_access_fl = arcpy.MakeFeatureLayer_management(food_access,'food_access_fl')
    neigh_gt40pct_res_fl = arcpy.MakeFeatureLayer_management(neigh_gt40pct_res,'neigh_gt40pct_res_fl')
    in_features = [neigh_gt40pct_res_fl, food_access_fl]
    out_class = 'neigh_gt40pct_res_intersect_food_access.shp'
    print("intersecting {} and {}: {}".format(food_access,neigh_gt40pct_res,out_class))
    arcpy.Intersect_analysis(in_features,out_class,'ALL')
    neigh_int_access = 'neigh_gt40pct_res_intersect_food_access.shp'
    print("intersect complete")
    
    # add geometry attributes for access_gt40pct_res_intersect.shp: POLY_AREA
    print("adding geometry attributes to {}".format(neigh_int_access))
    neigh_int_access_fl = arcpy.MakeFeatureLayer_management(neigh_int_access,'neigh_int_access_fl')
    arcpy.AddGeometryAttributes_management(neigh_int_access_fl,'AREA')
    print("done")
    
    # calculate weight for each record in food_access (area of record/area of neighborhood) : weight
    new_field = 'weight'
    print("adding a field to {}: {}".format(neigh_int_access,new_field))
    arcpy.AddField_management(neigh_int_access,new_field,'Double')
    calc = '!POLY_AREA!/!Shape_Area!'
    print("updating {} as {}".format(new_field, calc))
    arcpy.CalculateField_management(neigh_int_access,new_field,calc,"PYTHON_9.3","") 
    print("done")
    
    # calculate weighted score for each record (parcel) in food_access : prcl_score
    new_field = 'prcl_score'
    print("adding a field to {}: {}".format(neigh_int_access,new_field))
    arcpy.AddField_management(neigh_int_access,new_field,'Double')
    calc = '!access_num!*!weight!'
    print("updating {} as {}".format(new_field, calc))
    arcpy.CalculateField_management(neigh_int_access,new_field,calc,"PYTHON_9.3","") 
    print("done")
    
    # zonal statistics has a major bug and field mapping was returning zeros 
    # so I'm using cursors to calculate/update total scores per neighborhood
    
    sc = arcpy.da.SearchCursor(neigh_int_access,field_names=["NAME","prcl_score"])
    neigh_scores = {}
    
    # make dictionary containing [neighborhood: [all parcel scores for that neighborhood]] 
    for row in sc:
        neighborhood = row[0]
        prcl_score = row[1]
        if neigh_scores.has_key(neighborhood):
            neigh_scores[neighborhood].append(prcl_score)
        else: 
            neigh_scores[neighborhood]=[prcl_score]
    
    # update dictionary values as sum of parcel scores per neighborhood * 100
    for key in neigh_scores.keys():
        neigh_scores[key]=sum(neigh_scores[key])*100
    
    # add field to neighborhoods_gt40pct_res.shp: nbhd_score
    new_field = 'nbhd_score'
    print("adding a field to {}: {}".format(neigh_int_access,new_field))
    arcpy.AddField_management(neigh_gt40pct_res,new_field,'Double')
    
    # populate nbhd_score using update cursor
    print("updating {} as sum of prcl_scores by neighborhood".format(new_field))
    uc = arcpy.da.UpdateCursor(neigh_gt40pct_res,field_names=["NAME","nbhd_score"])
    for row in uc:
        for key in neigh_scores.keys():
            if row[0]==key:
                row[1]=neigh_scores[key]
                uc.updateRow(row)
    print("done")
    
    # delete intermediate files
    to_delete = [land_use,food_access,'DVRPC_2010_Land_Use_Feature_Service.shp'\
              ,'Walkable_Access_Healthy_Food.shp',residential,neigh_int_access,'land_use_res.shp'\
              ,wic,farmers_markets]
    for i in to_delete:
        print("deleting {}".format(i))
        arcpy.Delete_management(i)
    print("delete complete")
    print("analysis complete")


# CALL FUNCTIONS 

# download files
philadelphia_healthy_food_access_get_data(workspace)
# conduct analysis
philadelphia_healthy_food_access_analysis(workspace)


