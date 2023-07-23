#! /usr/bin/env python3
# This Python file uses the following encoding: utf-8
# Taken from: https://event.ifi.uni-heidelberg.de/?page_id=532

__author__ = 'jgeiss'

#############################################################################
# authors: Johanna Geiß, Heidelberg University, Germany                     #
# email: geiss@informatik.uni-heidelberg.de                                 #
# Copyright (c) 2017 Database Research Group,                               #
#               Institute of Computer Science,                              #
#               University of Heidelberg                                    #
#   Licensed under the Apache License, Version 2.0 (the "License");         #
#   you may not use this file except in compliance with the License.        #
#   You may obtain a copy of the License at                                 #
#                                                                           #
#   http://www.apache.org/licenses/LICENSE-2.0                              #
#                                                                           #
#   Unless required by applicable law or agreed to in writing, software     #
#   distributed under the License is distributed on an "AS IS" BASIS,       #
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.#
#   See the License for the specific language governing permissions and     #
#   limitations under the License.                                          #
#############################################################################
#      02.03.2017                                                           #
# last updated 21.3.2017 by Johanna Geiß                             #
#############################################################################
#  NECKAr: Named Entity Classifier for Wikidata                             #
#    this tool categorizes Wikidata items into 6 categories                 #
#    the parameters are set in NECKAr.cfg                                   #
#############################################################################

### Importing modules
import inspect
import sys
import configparser
from pymongo import *
from pymongo import errors
import NECKAr_get_functions as get_functions
from NECKAr_WikidataAPI import get_wikidata_item_tree_item_idsSPARQL
# from  NECKAr_wikidata_processor import WikiDataProcessor
import NECKAr_write_functions as write_functions

LABELS_TO_WIKIDATA_INT_IDS = {
    'ANG': ['Q315'],
    'DUC': ['Q431289'],
    'EVE': ['Q1656682'],
    'FAC': ['Q13226383'],
    'GPE': ['LOC'],
    # Stands for GeoPolitical Entitiy. Most are locations (LOC) but not only so need to add more stuff to the list
    'INFORMAL': [],  # ['P1449'],
    'LOC': ['Q115095765'], #This wikidata id isn't used, since relying on existing NECKAr code (function find_locations)
    'MISC': [],  # Should be ignored until further notice, here for completeness
    'ORG': ['Q43229'],
    'PER': ['Q5'],
    'TIMEX': ['Q11471'],
    'TTL': ['Q214339', 'Q177053'], #Note - only taking 'role' ('Q214339')
    'WOA': ['Q386724']
}




def print_info(info):
    print("INFO\tNECKAr:\t", info)


def read_config(config: configparser.ConfigParser):
    """Reads the configuration file NECKAr.cfg

    :param config: ConfigParser Object
    :return: input and output collection
    """

    host = config.get('Database', 'host')
    port = config.getint('Database', 'port')

    auth = config.getboolean('Database', 'auth')
    user = config.get('Database', 'user')
    password = config.get('Database', 'password')

    try:
        client = MongoClient(host, port)
    except errors.ConnectionFailure:
        print("Connection to the database cannot be made. Please check the config file")

    db_read_name = config.get('Database', 'db_dump')
    db_write_name = config.get('Database', 'db_write')
    db_in = client[db_read_name]  # Database from where information is extracted
    db_out = client[db_write_name]  # Database in which information is written
    if auth:
        db_out.authenticate(user, password)

    input_collection_name = config.get('Database', 'collection_dump')
    input_collection = db_in[input_collection_name]
    output_collection_name = config.get('Database', 'collection_write')
    output_collection = db_out[output_collection_name]
    print("Config File read in")
    return input_collection, output_collection


def find_persons(output_collection, input_collection):
    """Finds person in Wikidata dump and stores them together with additional information in the output collection

    :param output_collection:
    :param input_collection:
    :return: nothing, writes objects directly to MongoDB
    """

    per_insert = 0
    insert_count = 0
    bulk = output_collection.initialize_unordered_bulk_op()
    print_info("Find persons...")
    print_info("Remove all persons entries")
    output_collection.remove({"neClass": "PER"})
    print_info("--- DONE")
    person_cursor = input_collection.find(
        {"$and": [{"type": "item"}, {"claims.P31.mainsnak.datavalue.value.numeric-id": 5}]})
    print_info("Beginning of person-loop")
    for item in person_cursor:
        entry = write_functions.write_common_fields(item)
        entry["neClass"] = "PER"

        # date of birth
        dob = get_functions.get_datebirth(item)
        if dob:
            entry["date_birth"] = dob
        # date of death
        dod = get_functions.get_datedeath(item)
        if dod:
            entry["date_death"] = dod
        # gender
        gender = get_functions.get_gender(item)
        if gender:
            entry["gender"] = gender
        # occupation
        occupation = get_functions.get_occupation(item)
        if len(occupation) > 0:
            entry["occupation"] = occupation
        # aliases, alternative names
        alias = get_functions.get_alias_list(item)
        if len(alias) > 0:
            entry["alias"] = alias

        wdid = entry["id"]
        doc = output_collection.find_one({"id": wdid})
        if (not doc or doc["neClass"] != "PER"):
            insert_count += 1
            bulk.insert(entry)
        if insert_count == 1000:
            per_insert += 1
            print_info("PER " + str(per_insert * 1000) + "persons written")
            sys.stdout.flush()
            bulk.execute()
            bulk = output_collection.initialize_unordered_bulk_op()
            insert_count = 0
    if insert_count > 0:
        bulk.execute()


def find_locations(output_collection, input_collection):
    """
    Finds locations in Wikidata dump and stores them together with additional information in the output collection

    :param output_collection:
    :param input_collection:
    :return: nothing, writes objects directly to MongoDB
    """
    # Location Specific
    loc_insert = 0
    insert_count = 0
    bulk = output_collection.initialize_unordered_bulk_op()
    output_collection.remove({"neClass": "LOC"})
    print_info("LOC\tremoved old locations")

    geolocation_subclass = get_wikidata_item_tree_item_idsSPARQL([2221906], backward_properties=[279])
    food_subclass = get_wikidata_item_tree_item_idsSPARQL([2095], backward_properties=[279])
    geolocation_subclass = list(set(geolocation_subclass) - set(food_subclass))
    print_info("LOC\t" + str(len(geolocation_subclass)) + str(type(geolocation_subclass)))

    settlement_subclass = get_wikidata_item_tree_item_idsSPARQL([486972], backward_properties=[279])

    country_subclass = get_wikidata_item_tree_item_idsSPARQL([6256], backward_properties=[279])
    sovereignstate_subclass = get_wikidata_item_tree_item_idsSPARQL([3624078], backward_properties=[279])
    ccountry_subclass = get_wikidata_item_tree_item_idsSPARQL([1763527], backward_properties=[279])
    country_subclass += sovereignstate_subclass + ccountry_subclass

    sea_subclass = get_wikidata_item_tree_item_idsSPARQL([165], backward_properties=[279])
    state_subclass = get_wikidata_item_tree_item_idsSPARQL([7275], backward_properties=[279])
    city_subclass = get_wikidata_item_tree_item_idsSPARQL([515], backward_properties=[279])
    river_subclass = get_wikidata_item_tree_item_idsSPARQL([4022], backward_properties=[279])
    mountain_subclass = get_wikidata_item_tree_item_idsSPARQL([8502], backward_properties=[279])
    mountainr_subclass = get_wikidata_item_tree_item_idsSPARQL([1437459], backward_properties=[279])
    # POI_subclass= WikiDataProcessor.get_wikidata_item_tree_item_idsSPARQL([XXX], backward_properties=[279])
    hgte_subclass = get_wikidata_item_tree_item_idsSPARQL([15642541], backward_properties=[279])

    print_info("LOC\tLocation subclasses found")

    location_cursor = input_collection.find({"$and": [ \
        {"type": "item"}, \
        {"claims.P31.mainsnak.datavalue.value.numeric-id": {"$in": geolocation_subclass}}] \
        }, no_cursor_timeout=True)
    print_info("LOC\tLocations found")

    print_info("LOC\tBeginning of location-loop")
    for item in location_cursor:
        entry = write_functions.write_common_fields(item)
        entry["neClass"] = "LOC"

        (incountry, incontinent) = get_functions.get_location_inside(item)
        if len(incountry) != 0:
            entry["in_country"] = incountry
        if len(incontinent) != 0:
            entry["in_continent"] = incountry

        loc_type = get_functions.get_poi(item, country_subclass, settlement_subclass, city_subclass, sea_subclass,
                                         river_subclass, mountain_subclass, mountainr_subclass, state_subclass,
                                         hgte_subclass)
        if len(loc_type) != 0:
            entry["location_type"] = loc_type

        coordinate = get_functions.get_coordinate(item)
        if coordinate:
            # { type: "Point", coordinates: [ 40, 5 ] }
            entry["coordinate"] = coordinate

        population = get_functions.get_population(item)
        if population:
            entry["population"] = population

        # is part of LOD Link list
        # GN_ID = get_functions.get_geonamesID(item)
        # if GN_ID:
        #     entry["geonamesID"] = GN_ID

        wdid = entry["id"]
        doc = output_collection.find_one({"id": wdid})
        if (not doc or doc["neClass"] != "LOC"):
            insert_count += 1
            bulk.insert(entry)
            if insert_count == 1000:
                loc_insert += 1
                print_info("LOC\t" + str(loc_insert * 1000) + "locations written")
                sys.stdout.flush()

                try:
                    bulk.execute()
                except errors.BulkWriteError as bwe:
                    print(bwe.details)
                    # you can also take this component and do more analysis
                    # werrors = bwe.details['writeErrors']
                    raise
                bulk = output_collection.initialize_unordered_bulk_op()
                insert_count = 0
    location_cursor.close()
    if insert_count > 0:
        bulk.execute()


def find_organizations(output_collection, input_collection):
    """
    Finds organizations in Wikidata dump and stores them together with additional information in the output collection

    :param output_collection:
    :param input_collection:
    :return: nothing, writes objects directly to MongoDB
    """
    # Organization Specific
    org_insert = 0
    insert_count = 0
    bulk = output_collection.initialize_unordered_bulk_op()
    print_info("Beginning of Organization loop")
    output_collection.remove({"neClass": "ORG"})
    print_info("removed old orgs")
    organization_subclass = get_wikidata_item_tree_item_idsSPARQL([43229], backward_properties=[279])
    # print(len(organization_subclass))
    organization_cursor = input_collection.find({"$and": [{"type": "item"},
                                                          {"claims.P31.mainsnak.datavalue.value.numeric-id": {
                                                              "$in": organization_subclass}}]})

    for item in organization_cursor:
        entry = write_functions.write_common_fields(item)
        entry["neClass"] = "ORG"

        olang = get_functions.get_official_language(item)
        if len(olang) != 0:
            entry["official_language"] = olang

        inception = get_functions.get_inception(item)
        if inception:
            entry["inception"] = inception

        hq = get_functions.get_hq_location(item)
        if hq:
            entry["hq_location"] = hq

        web = get_functions.get_official_website(item)
        if web:
            entry["official_website"] = web

        founder = get_functions.get_founder(item)
        if len(founder) != 0:
            entry["founder"] = founder

        ceo = get_functions.get_ceo(item)
        if len(ceo) != 0:
            entry["ceo"] = ceo

        country_org = get_functions.get_country(item)
        if len(country_org) != 0:
            entry["country"] = country_org

        instanceof = get_functions.get_instance_of(item)
        if len(instanceof) != 0:
            entry["instance_of"] = instanceof

        wdid = entry["id"]
        doc = output_collection.find_one({"id": wdid})
        if (not doc or doc["neClass"] != "ORG"):
            insert_count += 1
            bulk.insert(entry)
            if insert_count == 1000:
                org_insert += 1
                print_info("ORG " + str(org_insert * 1000) + " organizations written")
                sys.stdout.flush()
                bulk.execute()
                bulk = output_collection.initialize_unordered_bulk_op()
                insert_count = 0
    if insert_count > 0:
        bulk.execute()


def find_events(output_collection, input_collection, should_get_date_of_official_opening: bool = False):
    """Finds events in Wikidata dump and stores them together with additional information in the output collection

       :param output_collection:
       :param input_collection:
       :param should_get_date_of_official_opening: should get date_of_official_opening (don't turn on unless implemented)
              <class 'bool'>
       :return: nothing, writes objects directly to MongoDB
       """

    eve_insert = 0
    insert_count = 0
    bulk = output_collection.initialize_unordered_bulk_op()
    print_info("Find events...")
    print_info("Remove all events entries")
    output_collection.remove({"neClass": "EVE"})
    print_info("--- DONE")
    event_subclass = get_wikidata_item_tree_item_idsSPARQL([1656682], backward_properties=[279])
    event_cursor = input_collection.find({"$and": [{"type": "item"},
                                                          {"claims.P31.mainsnak.datavalue.value.numeric-id": {
                                                              "$in": event_subclass}}]})
    print_info("Beginning of event-loop")
    for item in event_cursor:
        entry = write_functions.write_common_fields(item)
        entry["neClass"] = "EVE"

        if should_get_date_of_official_opening:
            dooo = get_functions.get_date_of_official_opening(item)
            if dooo:
                entry["date_of_official_opening"] = dooo
        event_location = get_functions.get_event_location(item)
        if event_location:
            entry["event_location"] = event_location

        wdid = entry["id"]
        doc = output_collection.find_one({"id": wdid})
        if (not doc or doc["neClass"] != "EVE"):
            insert_count += 1 #TODO - Q79838 gets here erroneously (it's an accordion!) https://www.wikidata.org/wiki/Q79838
            bulk.insert(entry)
        if insert_count == 1000:
            eve_insert += 1
            print_info("EVE " + str(eve_insert * 1000) + "events written")
            sys.stdout.flush()
            bulk.execute()
            bulk = output_collection.initialize_unordered_bulk_op()
            insert_count = 0
    if insert_count > 0:
        bulk.execute()

def find_languages(output_collection, input_collection):
    """Finds languages in Wikidata dump and stores them together with additional information in the output collection

       :param output_collection:
       :param input_collection:
       :return: nothing, writes objects directly to MongoDB
       """

    ang_insert = 0
    insert_count = 0
    bulk = output_collection.initialize_unordered_bulk_op()
    print_info("Find languages...")
    print_info("Remove all languages entries")
    output_collection.remove({"neClass": "ANG"})
    print_info("--- DONE")
    lang_cursor = input_collection.find(
        {"$and": [{"type": "item"}, {"claims.P31.mainsnak.datavalue.value.numeric-id": 315}]})
    print_info("Beginning of language-loop")
    for item in lang_cursor:
        entry = write_functions.write_common_fields(item)
        entry["neClass"] = "ANG"

        wdid = entry["id"]
        doc = output_collection.find_one({"id": wdid})
        if (not doc or doc["neClass"] != "ANG"):
            insert_count += 1
            bulk.insert(entry)
        if insert_count == 1000:
            ang_insert += 1
            print_info("ANG " + str(ang_insert * 1000) + "languages written")
            sys.stdout.flush()
            bulk.execute()
            bulk = output_collection.initialize_unordered_bulk_op()
            insert_count = 0
    if insert_count > 0:
        bulk.execute()

def find_brands(output_collection, input_collection):
    """Finds brands in Wikidata dump and stores them together with additional information in the output collection

       :param output_collection:
       :param input_collection:
       :return: nothing, writes objects directly to MongoDB
       """

    duc_insert = 0
    insert_count = 0
    bulk = output_collection.initialize_unordered_bulk_op()
    print_info("Find brands...")
    print_info("Remove all brands entries")
    output_collection.remove({"neClass": "DUC"})
    print_info("--- DONE")
    brand_cursor = input_collection.find(
        {"$and": [{"type": "item"}, {"claims.P31.mainsnak.datavalue.value.numeric-id": 431289}]})
    print_info("Beginning of brand-loop")
    for item in brand_cursor:
        entry = write_functions.write_common_fields(item)
        entry["neClass"] = "DUC"

        wdid = entry["id"]
        doc = output_collection.find_one({"id": wdid})
        if (not doc or doc["neClass"] != "DUC"):
            insert_count += 1
            bulk.insert(entry)
        if insert_count == 1000:
            duc_insert += 1
            print_info("DUC " + str(duc_insert * 1000) + "brands written")
            sys.stdout.flush()
            bulk.execute()
            bulk = output_collection.initialize_unordered_bulk_op()
            insert_count = 0
    if insert_count > 0:
        bulk.execute()

def find_facilities(output_collection, input_collection):
    """Finds facilities in Wikidata dump and stores them together with additional information in the output collection

       :param output_collection:
       :param input_collection:
       :return: nothing, writes objects directly to MongoDB
       """

    fac_insert = 0
    insert_count = 0
    bulk = output_collection.initialize_unordered_bulk_op()
    print_info("Find facilities...")
    print_info("Remove all facilities entries")
    output_collection.remove({"neClass": "FAC"})
    print_info("--- DONE")
    facility_subclass = get_wikidata_item_tree_item_idsSPARQL([13226383], backward_properties=[279])
    facility_cursor = input_collection.find({"$and": [{"type": "item"},
                                                          {"claims.P31.mainsnak.datavalue.value.numeric-id": {
                                                              "$in": facility_subclass}}]})

    print_info("Beginning of facility-loop")
    for item in facility_cursor:
        entry = write_functions.write_common_fields(item)
        entry["neClass"] = "FAC"

        wdid = entry["id"]
        doc = output_collection.find_one({"id": wdid})
        if (not doc or doc["neClass"] != "FAC"):
            insert_count += 1
            bulk.insert(entry)
        if insert_count == 1000:
            fac_insert += 1
            print_info("FAC " + str(fac_insert * 1000) + "facilities written")
            sys.stdout.flush()
            bulk.execute()
            bulk = output_collection.initialize_unordered_bulk_op()
            insert_count = 0
    if insert_count > 0:
        bulk.execute()


def find_time_instances(output_collection, input_collection):
    """Finds time instances in Wikidata dump and stores them together with additional information in the output collection

       :param output_collection:
       :param input_collection:
       :return: nothing, writes objects directly to MongoDB
       """

    timex_insert = 0
    insert_count = 0
    bulk = output_collection.initialize_unordered_bulk_op()
    print_info("Find time instances...")
    print_info("Remove all time instances entries")
    output_collection.remove({"neClass": "TIMEX"})
    print_info("--- DONE")
    time_subclass = get_wikidata_item_tree_item_idsSPARQL([11471], backward_properties=[279])
    time_cursor = input_collection.find({"$and": [{"type": "item"},
                                                          {"claims.P31.mainsnak.datavalue.value.numeric-id": {
                                                              "$in": time_subclass}}]})

    print_info("Beginning of time-loop")
    for item in time_cursor:
        entry = write_functions.write_common_fields(item)
        entry["neClass"] = "TIMEX"

        wdid = entry["id"]
        doc = output_collection.find_one({"id": wdid})
        if (not doc or doc["neClass"] != "TIMEX"):
            insert_count += 1
            bulk.insert(entry)
        if insert_count == 1000:
            timex_insert += 1
            print_info("TIMEX " + str(timex_insert * 1000) + "time instances written")
            sys.stdout.flush()
            bulk.execute()
            bulk = output_collection.initialize_unordered_bulk_op()
            insert_count = 0
    if insert_count > 0:
        bulk.execute()

########################################################################################################################

def find_titles(output_collection, input_collection):
    """Finds titles in Wikidata dump and stores them together with additional information in the output collection

       :param output_collection:
       :param input_collection:
       :return: nothing, writes objects directly to MongoDB
       """

    ttl_insert = 0
    insert_count = 0
    bulk = output_collection.initialize_unordered_bulk_op()
    print_info("Find titles...")
    print_info("Remove all titles entries")
    output_collection.remove({"neClass": "TTL"})
    print_info("--- DONE")
    title_subclass = get_wikidata_item_tree_item_idsSPARQL([214339], backward_properties=[279])
    title_cursor = input_collection.find({"$and": [{"type": "item"},
                                                          {"claims.P31.mainsnak.datavalue.value.numeric-id": {
                                                              "$in": title_subclass}}]})
    print_info("Beginning of title-loop")
    for item in title_cursor:
        entry = write_functions.write_common_fields(item)
        entry["neClass"] = "TTL"

        wdid = entry["id"]
        doc = output_collection.find_one({"id": wdid})
        if (not doc or doc["neClass"] != "TTL"):
            insert_count += 1  #TODO - Q20532, Q63440, Q31, Q78389 (probably because it's an instance of ´prince´) are mistakenly added here
            bulk.insert(entry)
        if insert_count == 1000:
            ttl_insert += 1
            print_info("TTL " + str(ttl_insert * 1000) + "titles written")
            sys.stdout.flush()
            bulk.execute()
            bulk = output_collection.initialize_unordered_bulk_op()
            insert_count = 0
    if insert_count > 0:
        bulk.execute()
def find_works(output_collection, input_collection):
    """Finds works in Wikidata dump and stores them together with additional information in the output collection

       :param output_collection:
       :param input_collection:
       :return: nothing, writes objects directly to MongoDB
       """

    woa_insert = 0
    insert_count = 0
    bulk = output_collection.initialize_unordered_bulk_op()
    print_info("Find works...")
    print_info("Remove all works entries")
    output_collection.remove({"neClass": "WOA"})
    print_info("--- DONE")
    work_cursor = input_collection.find(
        {"$and": [{"type": "item"}, {"claims.P31.mainsnak.datavalue.value.numeric-id": 38672}]})
    print_info("Beginning of work-loop")
    for item in work_cursor:
        entry = write_functions.write_common_fields(item)
        entry["neClass"] = "WOA"

        wdid = entry["id"]
        doc = output_collection.find_one({"id": wdid})
        if (not doc or doc["neClass"] != "WOA"):
            insert_count += 1 #TODO - Q38450, Q38666, Q38887 are mistakenly added here
            bulk.insert(entry)
        if insert_count == 1000:
            woa_insert += 1
            print_info("WOA " + str(woa_insert * 1000) + "works written")
            sys.stdout.flush()
            bulk.execute()
            bulk = output_collection.initialize_unordered_bulk_op()
            insert_count = 0
    if insert_count > 0:
        bulk.execute()


if __name__ == "__main__":
    """NECKAr: Named Entity Classifier for Wikidata

    this tool categorizes Wikidata items into 6 categories
    the parameters are set in NECKAr.cfg """

    config = configparser.ConfigParser()
    config.read('../NECKAr.cfg')

    input_collection, output_collection = read_config(config)
    output_collection.create_index([('id', ASCENDING)])

    if config.getboolean('Search_Flags', 'person'):
        find_persons(output_collection, input_collection)
    if config.getboolean('Search_Flags', 'location'):
        find_locations(output_collection, input_collection)
    if config.getboolean('Search_Flags', 'organization'):
        find_organizations(output_collection, input_collection)
    if config.getboolean('Search_Flags', 'event'):
        find_events(output_collection, input_collection)
    if config.getboolean('Search_Flags', 'language'):
        find_languages(output_collection, input_collection)
    if config.getboolean('Search_Flags', 'brand'):
        find_brands(output_collection, input_collection)
    if config.getboolean('Search_Flags', 'facility'):
        find_facilities(output_collection, input_collection)
    if config.getboolean('Search_Flags', 'time'):
        find_time_instances(output_collection, input_collection)
    if config.getboolean('Search_Flags', 'title'):
        find_titles(output_collection, input_collection)
    if config.getboolean('Search_Flags', 'work'):
        find_works(output_collection, input_collection)