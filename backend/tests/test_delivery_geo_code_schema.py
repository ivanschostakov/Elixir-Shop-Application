from src.integrations.delivery.geo.schemas.code import GeoCodeResult


def test_geocode_result_parses_bounds_and_precision() -> None:
    raw_payload = {
        "response": {
            "GeoObjectCollection": {
                "featureMember": [
                    {
                        "GeoObject": {
                            "metaDataProperty": {
                                "GeocoderMetaData": {
                                    "precision": "street",
                                    "text": "Тверская улица, Москва, Россия",
                                    "kind": "street",
                                    "Address": {
                                        "country_code": "ru",
                                        "postal_code": None,
                                    },
                                },
                            },
                            "name": "Тверская улица",
                            "description": "Москва, Россия",
                            "Point": {
                                "pos": "37.606478 55.763903",
                            },
                            "boundedBy": {
                                "Envelope": {
                                    "lowerCorner": "37.596516 55.756933",
                                    "upperCorner": "37.61547 55.769636",
                                },
                            },
                            "uri": "ymapsbm1://geo?data=test",
                        },
                    },
                ],
            },
        },
    }

    result = GeoCodeResult.from_raw(raw_payload)

    assert result.kind == "street"
    assert result.precision == "street"
    assert result.country_code == "RU"
    assert result.bounds is not None
    assert result.bounds.south_west.lon == 37.596516
    assert result.bounds.south_west.lat == 55.756933
    assert result.bounds.north_east.lon == 37.61547
    assert result.bounds.north_east.lat == 55.769636
