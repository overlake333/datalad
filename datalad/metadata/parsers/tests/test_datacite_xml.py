# emacs: -*- mode: python-mode; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Test datacite metadata parser """

from simplejson import dumps
from datalad.distribution.dataset import Dataset
from datalad.metadata.parsers.datacite import MetadataParser
from nose.tools import assert_equal
from datalad.tests.utils import with_tree
from datalad.tests.utils import assert_raises
from datalad.support.exceptions import IncompleteResultsError


@with_tree(tree={'.datalad': {'meta.datacite.xml': """\
<?xml version="1.0" encoding="UTF-8"?>
<resource xmlns="http://datacite.org/schema/kernel-2.2" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://datacite.org/schema/kernel-2.2 http://schema.datacite.org/meta/kernel-2.2/metadata.xsd">
	<identifier identifierType="DOI">10.6080/K0QN64NG</identifier>
	<creators>
		<creator>
			<creatorName>Last1, First1</creatorName>
		</creator>
		<creator>
			<creatorName>Last2, First2</creatorName>
		</creator>
	</creators>
	<titles>
		<title>Main
		        title</title>
		<title titleType="AlternativeTitle">CRCNS.org xxx-1</title>
	</titles>
	<publisher>CRCNS.org</publisher>
	<publicationYear>2011</publicationYear>
	<subjects>
		<subject>Neuroscience</subject>
		<subject>fMRI</subject>
	</subjects>
	<language>eng</language>
	<resourceType resourceTypeGeneral="Dataset">Dataset/Neurophysiology</resourceType>
	<sizes>
		<size>10 GB</size>
	</sizes>
	<formats>
		<format>application/matlab</format>
		<format>NIFTY</format>
	</formats>
	<version>1.0</version>
	<descriptions>
		<description descriptionType="Other">
                  Some long
                  description.
		</description>
	</descriptions>
	<relatedIdentifiers>
	    <relatedIdentifier relatedIdentifierType="DOI" relationType="IsDocumentedBy">10.1016/j.cub.2011.08.031</relatedIdentifier>
	</relatedIdentifiers>
</resource>
"""}})
def test_get_metadata(path):
    ds = Dataset(path).create(force=True)
    meta = MetadataParser(ds, [])._get_dataset_metadata()
    assert_equal(
        dumps(meta, sort_keys=True, indent=2),
        """\
{
  "author": [
    "Last1, First1",
    "Last2, First2"
  ],
  "citation": [
    "10.1016/j.cub.2011.08.031"
  ],
  "description": "Some long description.",
  "formats": [
    "application/matlab",
    "NIFTY"
  ],
  "name": "CRCNS.org xxx-1",
  "sameas": "10.6080/K0QN64NG",
  "shortdescription": "Main title",
  "tag": [
    "Neuroscience",
    "fMRI"
  ],
  "version": "1.0"
}""")
