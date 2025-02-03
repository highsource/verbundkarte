from SPARQLWrapper import get_sparql_dataframe
# for now, import SPARQLWrapper as well, to redefine __agent__:
import SPARQLWrapper 

import geopandas as gpd
import os
import pandas as pd
import urllib.request

USER_AGENT = "github.com/highsource/verbundkarte/0.0.1"
CACHE_DIR = '.cache'
OUT_DIR = 'out'
# WFS Service: https://sgx.geodatenzentrum.de/wfs_vg250-ew?REQUEST=GetCapabilities&SERVICE=WFS
VG250_URL = 'https://sgx.geodatenzentrum.de/wfs_vg250-ew?REQUEST=GetFeature&SERVICE=WFS&VERSION=2.0.0&outputFormat=json&typeNames=vg250-ew:vg250_krs&srsName=EPSG:4326&'
AUTHORITIES_FILE = 'data/authorities.csv'
ASSIGNMENTS_FILE = 'data/assignments.csv'
CACHED_VG250_PATH = os.path.join(CACHE_DIR, 'vg250_krs.json')
VG250_GEOFAKTOR_LAND_MIT_STRUKTUR = 4
ENHANCED_AUTHORITIES_PATH = os.path.join(OUT_DIR, 'authorities_enhanced.geojson')

def assert_dir_exists(path):
	if not os.path.exists(path):
		os.mkdir(path)

def download_if_not_cached(path, url):
	if not os.path.exists(path):
		urllib.request.urlretrieve(url, path)

def setup():
	assert_dir_exists(OUT_DIR)
	assert_dir_exists(CACHE_DIR)
	download_if_not_cached(CACHED_VG250_PATH, VG250_URL)

def get_wikidata_frame():

	endpoint = "https://query.wikidata.org/sparql"

	q = """
	    SELECT ?td ?tdLabel ?officalWebsite ?shortName ?twitterUserName ?linkedInOrgId
	    WHERE
	    {
	    # ?td isInstance transit district
	      ?td wdt:P31 wd:Q7835189.
	      ?td wdt:P17 wd:Q183.
	      OPTIONAL {?td wdt:P856 ?officalWebsite}
	      OPTIONAL {?td wdt:P1813 ?shortName}
	      OPTIONAL {?td wdt:P2002 ?twitterUserName}
	      OPTIONAL {?td wdt:P4264 ?linkedInOrgId}
	      SERVICE wikibase:label { bd:serviceParam wikibase:language "de". }
	    }
	"""

	# TODO In case https://github.com/RDFLib/sparqlwrapper/pull/225 is merged
	# these two lines may be replaced by the param version below
	SPARQLWrapper.__agent__ = USER_AGENT
	df = get_sparql_dataframe(endpoint, q)
	# df = get_sparql_dataframe(endpoint, q, USER_AGENT)
	
	df.td = df.td.str.replace('http://www.wikidata.org/entity/' , '', regex=True)
	return df

def merge():
	"""
	Joins authorities, their operating areas and corresponding shapes
	and writes the resulting file to ENHANCED_AUTHORITIES_PATH.  
	"""
	authorities = pd.read_csv(AUTHORITIES_FILE)
	# Import assignments. As district ID may have leading zeros, need to set as str explicitly
	assignments = pd.read_csv(ASSIGNMENTS_FILE, dtype = {'kreis': str})

	all_districts = gpd.read_file(CACHED_VG250_PATH)
	gf4_districts = all_districts[(all_districts.gf==VG250_GEOFAKTOR_LAND_MIT_STRUKTUR)]

	# Merge districts with assignments. Note, that to keep GeoDataFrame, we use merge called on gf4_districts
	assignments_with_geometries = gf4_districts.merge(assignments, right_on='kreis', left_on='ars').filter(items=['kreis','org','geometry'])
	assignments_with_geometries_grouped_by_org = assignments_with_geometries.dissolve(by='org')
	authorities_with_geometries = assignments_with_geometries_grouped_by_org.merge(authorities, how='outer', on='org')
	authorities_with_geometries = authorities_with_geometries.merge(get_wikidata_frame(), how='left', left_on='wikidata', right_on='td')
	authorities_with_geometries.to_file(ENHANCED_AUTHORITIES_PATH, driver='GeoJSON')

setup()
merge()
