"""Trading API package weight XML.

eBay rejects Authenticity-Guarantee-eligible items (high-value sneakers,
handbags, watches) with error 717 when no package weight is supplied, because
eBay generates the authentication shipping label. The Trading API listing must
always include ShippingPackageDetails with a weight.
"""
import re
from backend.app.services.ebay.trading import build_shipping_package_xml


def _major_minor(xml):
    major = re.search(r'<WeightMajor[^>]*>(\d+)</WeightMajor>', xml)
    minor = re.search(r'<WeightMinor[^>]*>(\d+)</WeightMinor>', xml)
    return int(major.group(1)), int(minor.group(1))


def test_converts_pounds_and_ounces():
    xml = build_shipping_package_xml(2.5)
    assert _major_minor(xml) == (2, 8)          # 0.5 lb = 8 oz


def test_whole_pounds():
    assert _major_minor(build_shipping_package_xml(3.0)) == (3, 0)


def test_under_one_pound():
    assert _major_minor(build_shipping_package_xml(0.75)) == (0, 12)


def test_none_uses_default_weight():
    # Must still emit a valid, non-zero weight so eBay 717 cannot fire.
    major, minor = _major_minor(build_shipping_package_xml(None))
    assert (major, minor) != (0, 0)


def test_zero_or_negative_uses_default():
    assert _major_minor(build_shipping_package_xml(0)) == _major_minor(build_shipping_package_xml(None))
    assert _major_minor(build_shipping_package_xml(-5)) == _major_minor(build_shipping_package_xml(None))


def test_contains_shipping_package_details_element():
    xml = build_shipping_package_xml(2.5)
    assert '<ShippingPackageDetails>' in xml
    assert '</ShippingPackageDetails>' in xml


def test_rounds_ounces_to_whole_number():
    # 1.1 lb -> 1 lb 1.6 oz -> rounds to 2 oz, never a fraction
    major, minor = _major_minor(build_shipping_package_xml(1.1))
    assert major == 1
    assert minor in (1, 2)  # rounding tolerance
