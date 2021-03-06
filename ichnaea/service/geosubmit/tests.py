import time

from ichnaea.models import (
    Cell,
    CellObservation,
    Radio,
    User,
    Wifi,
    WifiObservation,
)
from ichnaea.tests.base import CeleryAppTestCase
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)
from ichnaea.util import utcnow


class TestGeoSubmit(CeleryAppTestCase):

    def test_ok_cell(self):
        session = self.session
        cell = CellFactory()
        new_cell = CellFactory.build()
        session.flush()

        res = self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": cell.lat,
                 "longitude": cell.lon,
                 "radioType": cell.radio.name,
                 "cellTowers": [{
                     "mobileCountryCode": cell.mcc,
                     "mobileNetworkCode": cell.mnc,
                     "locationAreaCode": cell.lac,
                     "cellId": cell.cid,
                 }]},
                {"latitude": new_cell.lat,
                 "longitude": new_cell.lon,
                 "cellTowers": [{
                     "radioType": new_cell.radio.name,
                     "mobileCountryCode": new_cell.mcc,
                     "mobileNetworkCode": new_cell.mnc,
                     "locationAreaCode": new_cell.lac,
                     "cellId": new_cell.cid,
                 }]},
            ]},
            status=200)

        # check that we get an empty response
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {})

        self.assertEqual(session.query(Cell).count(), 2)
        observations = session.query(CellObservation).all()
        self.assertEqual(len(observations), 2)
        radios = set([obs.radio for obs in observations])
        self.assertEqual(radios, set([cell.radio, new_cell.radio]))

        self.check_stats(
            counter=['geosubmit.api_key.test',
                     'items.api_log.test.uploaded.batches',
                     'items.api_log.test.uploaded.reports',
                     'items.api_log.test.uploaded.cell_observations',
                     'items.uploaded.cell_observations',
                     'items.uploaded.batches',
                     'items.uploaded.reports',
                     'request.v1.geosubmit.200',
                     ],
            timer=['items.api_log.test.uploaded.batch_size',
                   'items.uploaded.batch_size',
                   'request.v1.geosubmit'])

    def test_ok_no_existing_cell(self):
        session = self.session
        now_ms = int(time.time() * 1000)
        first_of_month = utcnow().replace(day=1, hour=0, minute=0, second=0)
        cell = CellFactory.build()

        res = self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": cell.lat,
                 "longitude": cell.lon,
                 "accuracy": 12.4,
                 "altitude": 100.1,
                 "altitudeAccuracy": 23.7,
                 "heading": 45.0,
                 "speed": 3.6,
                 "timestamp": now_ms,
                 "cellTowers": [{
                     "radioType": cell.radio.name,
                     "mobileCountryCode": cell.mcc,
                     "mobileNetworkCode": cell.mnc,
                     "locationAreaCode": cell.lac,
                     "cellId": cell.cid,
                     "age": 3,
                     "asu": 31,
                     "psc": cell.psc,
                     "signalStrength": -51,
                     "timingAdvance": 1,
                 }]},
            ]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {})

        self.assertEquals(session.query(Cell).count(), 1)
        result = session.query(CellObservation).all()
        self.assertEquals(len(result), 1)
        obs = result[0]
        for name in ('lat', 'lon', 'radio', 'mcc', 'mnc', 'lac', 'cid', 'psc'):
            self.assertEqual(getattr(obs, name), getattr(cell, name))
        self.assertEqual(obs.accuracy, 12)
        self.assertEqual(obs.altitude, 100)
        self.assertEqual(obs.altitude_accuracy, 24)
        self.assertEqual(obs.heading, 45.0)
        self.assertEqual(obs.speed, 3.6)
        self.assertEqual(obs.time, first_of_month)
        self.assertEqual(obs.asu, 31)
        self.assertEqual(obs.signal, -51)
        self.assertEqual(obs.ta, 1)

    def test_ok_partial_cell(self):
        session = self.session
        cell = CellFactory()
        session.flush()

        res = self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": cell.lat,
                 "longitude": cell.lon,
                 "cellTowers": [{
                     "radioType": cell.radio.name,
                     "mobileCountryCode": cell.mcc,
                     "mobileNetworkCode": cell.mnc,
                     "locationAreaCode": cell.lac,
                     "cellId": cell.cid,
                     "psc": cell.psc}, {
                     "radioType": cell.radio.name,
                     "mobileCountryCode": cell.mcc,
                     "mobileNetworkCode": cell.mnc,
                     "psc": cell.psc + 1,
                 }]},
            ]},
            status=200)

        # check that we get an empty response
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {})

        observations = session.query(CellObservation).all()
        self.assertEqual(len(observations), 2)
        pscs = set([obs.psc for obs in observations])
        self.assertEqual(pscs, set([cell.psc, cell.psc + 1]))

    def test_ok_wifi(self):
        session = self.session
        wifis = WifiFactory.create_batch(4)
        new_wifi = WifiFactory()
        session.flush()
        res = self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [{
                "latitude": wifis[0].lat,
                "longitude": wifis[0].lon,
                "wifiAccessPoints": [
                    {"macAddress": wifis[0].key},
                    {"macAddress": wifis[1].key},
                    {"macAddress": wifis[2].key},
                    {"macAddress": wifis[3].key},
                    {"macAddress": new_wifi.key},
                ]},
            ]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {})

        # Check that new wifi exists
        query = session.query(Wifi)
        count = query.filter(Wifi.key == new_wifi.key).count()
        self.assertEquals(count, 1)

        # check that WifiObservation records are created
        self.assertEquals(session.query(WifiObservation).count(), 5)

        self.check_stats(
            counter=['items.api_log.test.uploaded.batches',
                     'items.api_log.test.uploaded.reports',
                     'items.api_log.test.uploaded.wifi_observations',
                     'items.uploaded.wifi_observations',
                     ],
            timer=['items.api_log.test.uploaded.batch_size'])

    def test_ok_no_existing_wifi(self):
        session = self.session
        wifi = WifiFactory.build()

        res = self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": wifi.lat,
                 "longitude": wifi.lon,
                 "wifiAccessPoints": [{
                     "macAddress": wifi.key,
                     "age": 3,
                     "channel": 6,
                     "frequency": 2437,
                     "signalToNoiseRatio": 13,
                     "signalStrength": -77,
                 }]},
            ]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {})

        # Check that wifi exists
        query = session.query(Wifi)
        count = query.filter(Wifi.key == wifi.key).count()
        self.assertEquals(count, 1)

        # check that WifiObservation records are created
        result = session.query(WifiObservation).all()
        self.assertEquals(len(result), 1)
        obs = result[0]
        self.assertEqual(obs.lat, wifi.lat)
        self.assertEqual(obs.lon, wifi.lon)
        self.assertEqual(obs.key, wifi.key)
        self.assertEqual(obs.channel, 6)
        self.assertEqual(obs.signal, -77)
        self.assertEqual(obs.snr, 13)

    def test_invalid_json(self):
        session = self.session
        wifi = WifiFactory.build()
        self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": wifi.lat,
                 "longitude": wifi.lon,
                 "wifiAccessPoints": [{
                     "macAddress": 10,
                 }]},
            ]},
            status=400)
        self.assertEquals(session.query(WifiObservation).count(), 0)

    def test_invalid_latitude(self):
        session = self.session
        wifi = WifiFactory.build()
        self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": 12345.0,
                 "longitude": wifi.lon,
                 "wifiAccessPoints": [{
                     "macAddress": wifi.key,
                 }]},
            ]},
            status=200)
        self.assertEquals(session.query(WifiObservation).count(), 0)

    def test_invalid_cell(self):
        cell = CellFactory.build()
        self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": cell.lat,
                 "longitude": cell.lon,
                 "cellTowers": [{
                     "radioType": cell.radio.name,
                     "mobileCountryCode": cell.mcc,
                     "mobileNetworkCode": 2000,
                     "locationAreaCode": cell.lac,
                     "cellId": cell.cid,
                 }]},
            ]},
            status=200)
        self.assertEquals(self.session.query(CellObservation).count(), 0)

    def test_invalid_radiotype(self):
        cell = CellFactory.build()
        cell2 = CellFactory.build(radio=Radio.wcdma)
        self.app.post_json(
            '/v1/geosubmit?key=test',
            {'items': [
                {'latitude': cell.lat,
                 'longitude': cell.lon,
                 'cellTowers': [{
                     'radioType': '18',
                     'mobileCountryCode': cell.mcc,
                     'mobileNetworkCode': cell.mnc,
                     'locationAreaCode': cell.lac,
                     'cellId': cell.cid,
                 }, {
                     'radioType': 'umts',
                     'mobileCountryCode': cell2.mcc,
                     'mobileNetworkCode': cell2.mnc,
                     'locationAreaCode': cell2.lac,
                     'cellId': cell2.cid,
                 }]},
            ]},
            status=200)
        obs = self.session.query(CellObservation).all()
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0].cid, cell2.cid)

    def test_duplicated_cell_observations(self):
        session = self.session
        cell = CellFactory.build()
        self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": cell.lat,
                 "longitude": cell.lon,
                 "cellTowers": [
                     {"radioType": cell.radio.name,
                      "mobileCountryCode": cell.mcc,
                      "mobileNetworkCode": cell.mnc,
                      "locationAreaCode": cell.lac,
                      "cellId": cell.cid,
                      "asu": 10},
                     {"radioType": cell.radio.name,
                      "mobileCountryCode": cell.mcc,
                      "mobileNetworkCode": cell.mnc,
                      "locationAreaCode": cell.lac,
                      "cellId": cell.cid,
                      "asu": 16},
                 ]},
            ]},
            status=200)
        self.assertEquals(session.query(CellObservation).count(), 1)

    def test_duplicated_wifi_observations(self):
        session = self.session
        wifi = WifiFactory.build()
        self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [
                {"latitude": wifi.lat,
                 "longitude": wifi.lon,
                 "wifiAccessPoints": [
                     {"macAddress": wifi.key,
                      "signalStrength": -92},
                     {"macAddress": wifi.key,
                      "signalStrength": -77},
                 ]},
            ]},
            status=200)
        self.assertEquals(session.query(WifiObservation).count(), 1)

    def test_email_header(self):
        nickname = 'World Tr\xc3\xa4veler'
        email = 'world_tr\xc3\xa4veler@email.com'
        session = self.session
        wifis = WifiFactory.create_batch(2)
        self.app.post_json(
            '/v1/geosubmit?key=test',
            {"items": [{
                "latitude": wifis[0].lat,
                "longitude": wifis[0].lon,
                "wifiAccessPoints": [
                    {"macAddress": wifis[0].key},
                    {"macAddress": wifis[1].key},
                ]},
            ]},
            headers={
                'X-Nickname': nickname,
                'X-Email': email,
            },
            status=200)

        session = self.session
        result = session.query(User).all()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].email, email.decode('utf-8'))

    def test_batches(self):
        session = self.session
        batch_size = 110
        wifis = WifiFactory.create_batch(batch_size)
        items = [{"latitude": wifis[i].lat,
                  "longitude": wifis[i].lon + (i / 10000.0),
                  "wifiAccessPoints": [{"macAddress": wifis[i].key}]}
                 for i in range(batch_size)]

        # let's add a bad one, this will just be skipped
        items.append({'lat': 10, 'lon': 10, 'whatever': 'xx'})
        self.app.post_json('/v1/geosubmit?key=test',
                           {"items": items}, status=200)

        result = session.query(WifiObservation).all()
        self.assertEqual(len(result), batch_size)
