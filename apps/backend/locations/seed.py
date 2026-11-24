import json
from decimal import Decimal
from pathlib import Path

from django.db import transaction

from .models import NigerianLGA, NigerianState, NigerianWard, PollingUnit
from .nigeria_lgas import NIGERIA_ALL_774_LGAS

# All 36 States + FCT Abuja with geopolitical zones and INEC state codes
ALL_NIGERIAN_STATES: list[tuple[str, str, str]] = [
    ("Abia", "AB", "South East"),
    ("Adamawa", "AD", "North East"),
    ("Akwa Ibom", "AK", "South South"),
    ("Anambra", "AN", "South East"),
    ("Bauchi", "BA", "North East"),
    ("Bayelsa", "BY", "South South"),
    ("Benue", "BE", "North Central"),
    ("Borno", "BO", "North East"),
    ("Cross River", "CR", "South South"),
    ("Delta", "DE", "South South"),
    ("Ebonyi", "EB", "South East"),
    ("Edo", "ED", "South South"),
    ("Ekiti", "EK", "South West"),
    ("Enugu", "EN", "South East"),
    ("FCT Abuja", "FC", "North Central"),
    ("Gombe", "GO", "North East"),
    ("Imo", "IM", "South East"),
    ("Jigawa", "JI", "North West"),
    ("Kaduna", "KD", "North West"),
    ("Kano", "KN", "North West"),
    ("Katsina", "KT", "North West"),
    ("Kebbi", "KB", "North West"),
    ("Kogi", "KG", "North Central"),
    ("Kwara", "KW", "North Central"),
    ("Lagos", "LA", "South West"),
    ("Nasarawa", "NA", "North Central"),
    ("Niger", "NI", "North Central"),
    ("Ogun", "OG", "South West"),
    ("Ondo", "ON", "South West"),
    ("Osun", "OS", "South West"),
    ("Oyo", "OY", "South West"),
    ("Plateau", "PL", "North Central"),
    ("Rivers", "RI", "South South"),
    ("Sokoto", "SO", "North West"),
    ("Taraba", "TA", "North East"),
    ("Yobe", "YO", "North East"),
    ("Zamfara", "ZA", "North West"),
]

# Detailed hyper-local Nigeria hierarchy: State -> LGA -> Ward -> Polling Units
# Format:
# { state_code: { lga_name: { ward_name: [(pu_code, pu_name, landmark, lat, lon), ...] } } }
DETAILED_LOCATIONS: dict[str, dict[str, dict[str, list[tuple[str, str, str, str, str]]]]] = {
    "LA": {
        "Ikeja": {
            "Anifowoshe / Ikeja": [
                ("LA/11/01/001", "Open Space by Allen Roundabout", "Allen Avenue / Obafemi Awolowo Way", "6.601838", "3.351486"),
                ("LA/11/01/002", "In Front of Computer Village Gate", "Otigba Street, Ikeja", "6.594420", "3.342210"),
                ("LA/11/01/003", "Anifowoshe Primary School", "Simbiat Abiola Way, Ikeja", "6.598910", "3.347820"),
            ],
            "Opebi / Allen": [
                ("LA/11/02/001", "Opebi Link Bridge Junction", "Opebi Road, Ikeja", "6.596610", "3.361450"),
                ("LA/11/02/002", "Toyin Street Market Open Space", "Toyin Street / Allen", "6.595110", "3.354780"),
                ("LA/11/02/003", "Salvation Bus Stop Open Space", "Opebi Road", "6.599840", "3.358910"),
            ],
            "Alausa / Oregun": [
                ("LA/11/03/001", "Alausa Secretariat Gate Open Space", "Obafemi Awolowo Way, Alausa", "6.614310", "3.358120"),
                ("LA/11/03/002", "Oregun Kudirat Abiola Bus Stop", "Kudirat Abiola Way, Oregun", "6.607540", "3.364210"),
            ],
        },
        "Eti-Osa": {
            "Victoria Island I": [
                ("LA/08/01/001", "Adeola Odeku Junction Open Space", "Adeola Odeku Street, VI", "6.428110", "3.421950"),
                ("LA/08/01/002", "Ahmadu Bello Way / Bar Beach Gate", "Ahmadu Bello Way, VI", "6.425210", "3.428820"),
                ("LA/08/01/003", "Sanusi Fafunwa Street Open Space", "Near Eko Hotel Roundabout", "6.431050", "3.431400"),
            ],
            "Lekki Phase I / Ikate": [
                ("LA/08/02/001", "Admiralty Way Roundabout", "Lekki Phase 1 Gate", "6.447820", "3.472310"),
                ("LA/08/02/002", "Ikate Elegushi Junction", "Lekki-Epe Expressway, Ikate", "6.437510", "3.489210"),
                ("LA/08/02/003", "Freedom Way Open Space", "Lekki Phase 1", "6.444120", "3.479500"),
            ],
            "Ajah / Sangotedo": [
                ("LA/08/03/001", "Ajah Under-Bridge Market Square", "Ajah Roundabout", "6.469810", "3.565410"),
                ("LA/08/03/002", "Abraham Adesanya Estate Gate", "Lekki-Epe Expressway, Ajah", "6.465120", "3.588210"),
            ],
        },
        "Surulere": {
            "Bode Thomas / Shitta": [
                ("LA/20/01/001", "Bode Thomas / Adeniran Ogunsanya", "Leisure Mall Axis, Surulere", "6.497210", "3.356810"),
                ("LA/20/01/002", "National Stadium Main Gate Open Space", "Western Avenue, Surulere", "6.497820", "3.364510"),
                ("LA/20/01/003", "Shitta Roundabout Open Space", "Shitta, Surulere", "6.501540", "3.353120"),
            ],
            "Aguda / Ijesha": [
                ("LA/20/02/001", "Aguda Market Primary School", "Enitan Street, Aguda", "6.492310", "3.341820"),
                ("LA/20/02/002", "Ijesha Bus Stop Open Space", "Oshodi-Apapa Expressway", "6.505120", "3.332450"),
            ],
        },
        "Lagos Mainland": {
            "Yaba / Igbobi": [
                ("LA/15/01/001", "Yaba Tech Front Gate Open Space", "Herbert Macaulay Way, Yaba", "6.517210", "3.374210"),
                ("LA/15/01/002", "Sabo Market Square", "Commercial Avenue, Sabo Yaba", "6.509410", "3.377520"),
                ("LA/15/01/003", "Tejuosho Ultra-Modern Market Gate", "Tejuosho, Yaba", "6.509810", "3.368210"),
            ],
            "Ebute Metta": [
                ("LA/15/02/001", "Oyingbo Market Open Space", "Oyingbo Bus Terminal", "6.477810", "3.381210"),
                ("LA/15/02/002", "Adekunle Junction Open Space", "Third Mainland Axis", "6.494510", "3.385120"),
            ],
        },
        "Kosofe": {
            "Gbagada Phase II / Pedro": [
                ("LA/13/01/001", "Gbagada General Hospital Gate", "Hospital Road, Gbagada", "6.553210", "3.388120"),
                ("LA/13/01/002", "Charley Boy Bus Stop Open Space", "Gbagada Expressway", "6.556820", "3.379210"),
            ],
            "Ketu / Alapere": [
                ("LA/13/02/001", "Ketu Mile 12 Market Junction", "Ikorodu Road, Ketu", "6.601210", "3.394120"),
                ("LA/13/02/002", "Alapere Estate Main Gate", "Alapere, Ketu", "6.588910", "3.397410"),
            ],
        },
        "Alimosho": {
            "Egbeda / Alimosho": [
                ("LA/03/01/001", "Egbeda Bus Stop Roundabout", "Akowonjo Road, Egbeda", "6.597410", "3.291210"),
                ("LA/03/01/002", "Akowonjo Primary School", "Shasha Road, Akowonjo", "6.603210", "3.304510"),
            ],
            "Ikotun / Idimu": [
                ("LA/03/02/001", "Ikotun Market Roundabout", "Ikotun-Idimu Road", "6.551210", "3.268410"),
                ("LA/03/02/002", "Idimu Council Secretariat Gate", "Idimu Road", "6.578120", "3.281510"),
            ],
        },
    },
    "FC": {
        "Abuja Municipal (AMAC)": {
            "Wuse": [
                ("FC/06/01/001", "Wuse Market Main Gate Open Space", "Herbert Macaulay Way, Wuse Zone 5", "9.064310", "7.465210"),
                ("FC/06/01/002", "Aminu Kano Crescent / Banex Plaza", "Wuse II, Abuja", "9.076510", "7.472810"),
                ("FC/06/01/003", "Adetokunbo Ademola Crescent Junction", "Wuse II Commercial Corridor", "9.078920", "7.481210"),
            ],
            "Garki": [
                ("FC/06/02/001", "Area 1 Shopping Complex Open Space", "Garki Area 1", "9.033210", "7.469810"),
                ("FC/06/02/002", "Garki Ultra-Modern Market Gate", "Garki II, Abuja", "9.026510", "7.493210"),
            ],
            "Gwarinpa": [
                ("FC/06/03/001", "3rd Avenue / First Avenue Junction", "Gwarinpa Estate, Abuja", "9.109810", "7.405210"),
                ("FC/06/03/002", "Charlie Boy / 6th Avenue Market", "Gwarinpa, Abuja", "9.115420", "7.412310"),
            ],
            "Maitama": [
                ("FC/06/04/001", "Farmers Market Open Space", "Maitama District", "9.088120", "7.496510"),
                ("FC/06/04/002", "Ibrahim Babangida Way Junction", "Maitama, Abuja", "9.091210", "7.501210"),
            ],
        },
        "Bwari": {
            "Kubwa": [
                ("FC/02/01/001", "Kubwa Village Market Open Space", "Gado Nasko Road, Kubwa", "9.153810", "7.322410"),
                ("FC/02/01/002", "Phase 4 Primary School Gate", "Kubwa Phase 4", "9.160210", "7.331510"),
            ],
            "Dutse Alhaji": [
                ("FC/02/02/001", "Dutse Market Square", "Dutse-Bwari Road", "9.139210", "7.372410"),
                ("FC/02/02/002", "Sokale Junction Open Space", "Dutse Alhaji", "9.144510", "7.368910"),
            ],
        },
        "Gwagwalada": {
            "Gwagwalada Central": [
                ("FC/03/01/001", "Specialist Hospital Junction", "Gwagwalada Main Road", "8.943210", "7.081410"),
                ("FC/03/01/002", "UniAbuja Mini Campus Gate", "Gwagwalada", "8.951210", "7.078510"),
            ],
        },
    },
    "RI": {
        "Port Harcourt": {
            "New GRA / Phase II": [
                ("RI/15/01/001", "Tombia Extension Junction", "New GRA Phase 2, PH", "4.824110", "7.001210"),
                ("RI/15/01/002", "Olu Obasanjo Road / Waterlines", "Waterlines Junction, PH", "4.815210", "7.011410"),
            ],
            "Diobu / Mile 1": [
                ("RI/15/02/001", "Mile 1 Market Main Gate", "Ikwerre Road, Diobu", "4.791210", "6.998510"),
                ("RI/15/02/002", "Mile 3 Park Open Space", "Ikwerre Road, Mile 3", "4.804510", "6.989210"),
            ],
        },
        "Obio/Akpor": {
            "Rumuokoro / Choba": [
                ("RI/13/01/001", "Rumuokoro Roundabout Open Space", "East-West Road, Rumuokoro", "4.868210", "6.998410"),
                ("RI/13/01/002", "UniPort Choba Gate", "Choba, Port Harcourt", "4.896510", "6.912510"),
            ],
            "Rumuola / Woji": [
                ("RI/13/02/001", "Rumuola Flyover Open Space", "Aba Road, Rumuola", "4.832110", "7.005410"),
                ("RI/13/02/002", "Woji Town Hall Square", "Woji Road, Obio/Akpor", "4.828910", "7.054110"),
            ],
        },
    },
    "OY": {
        "Ibadan North": {
            "Bodija / UI": [
                ("OY/06/01/001", "Bodija Market Main Gate", "Old Bodija, Ibadan", "7.434210", "3.914510"),
                ("OY/06/01/002", "University of Ibadan Main Gate", "Oyo Road, Ibadan", "7.443210", "3.900110"),
            ],
            "Mokola / Sango": [
                ("OY/06/02/001", "Mokola Roundabout Cultural Centre", "Mokola Hill, Ibadan", "7.404510", "3.892110"),
                ("OY/06/02/002", "Sango Polytechnic Junction", "Sango-Eleyele Road", "7.422110", "3.896510"),
            ],
        },
        "Ibadan South-West": {
            "Ring Road / Challenge": [
                ("OY/08/01/001", "Ring Road Mobil Junction", "Ring Road, Ibadan", "7.362110", "3.864510"),
                ("OY/08/01/002", "Challenge Bus Terminal Open Space", "Challenge, Ibadan", "7.345210", "3.878110"),
            ],
        },
    },
    "KN": {
        "Kano Municipal": {
            "Zango / Kurmi": [
                ("KN/20/01/001", "Kurmi Market Main Entrance", "Old City, Kano", "12.002110", "8.516710"),
                ("KN/20/01/002", "Kofar Mata Primary School", "Kofar Mata, Kano", "12.006510", "8.524110"),
            ],
        },
        "Nassarawa": {
            "Sabon Gari / GRA": [
                ("KN/28/01/001", "Sabon Gari Market Gate", "Ahmadu Bello Way, Kano", "12.012410", "8.538210"),
                ("KN/28/01/002", "Murtala Mohammed Way Open Space", "Nassarawa GRA, Kano", "11.998510", "8.554110"),
            ],
        },
    },
    "OG": {
        "Ado-Odo/Ota": {
            "Ota I / Sango": [
                ("OG/03/01/001", "Sango Ota Under-Bridge Open Space", "Lagos-Abeokuta Expressway", "6.707210", "3.245110"),
                ("OG/03/01/002", "Covenant University Gate Axis", "Idiroko Road, Ota", "6.671810", "3.158210"),
            ],
        },
        "Abeokuta South": {
            "Kuto / Panseke": [
                ("OG/02/01/001", "Panseke Market Square", "Panseke, Abeokuta", "7.147510", "3.346110"),
                ("OG/02/01/002", "Kuto Motor Park Open Space", "Kuto, Abeokuta", "7.141210", "3.354210"),
            ],
        },
    },
    "EN": {
        "Enugu North": {
            "New Haven / Independence Layout": [
                ("EN/04/01/001", "New Haven Junction Open Space", "Chime Avenue, Enugu", "6.458210", "7.523410"),
                ("EN/04/01/002", "Okpara Square Main Gate", "Independence Layout, Enugu", "6.442110", "7.515210"),
            ],
            "Ogui / Ogbete": [
                ("EN/04/02/001", "Ogbete Main Market Square", "Market Road, Enugu", "6.435210", "7.488210"),
            ],
        },
    },
    "KD": {
        "Kaduna North": {
            "Unguwan Rimi / Malali": [
                ("KD/09/01/001", "Ahmadu Bello Way / Leventis Roundabout", "Kaduna Central", "10.522210", "7.438210"),
                ("KD/09/01/002", "Unguwan Rimi Primary School", "Unguwan Rimi, Kaduna", "10.538110", "7.454110"),
            ],
        },
        "Kaduna South": {
            "Barnawa / Kakuri": [
                ("KD/10/01/001", "Barnawa Market Square", "Barnawa Complex, Kaduna", "10.481210", "7.431210"),
            ],
        },
    },
    "AN": {
        "Awka South": {
            "Awka Ward I (Aroma)": [
                ("AN/06/01/001", "Aroma Junction Open Space", "Enugu-Onitsha Expressway, Awka", "6.222110", "7.081210"),
                ("AN/06/01/002", "Eke Awka Market Gate", "Zik Avenue, Awka", "6.208210", "7.068110"),
            ],
        },
        "Onitsha North": {
            "Inland Town / Main Market": [
                ("AN/16/01/001", "Onitsha Main Market Open Space", "Bright Street, Onitsha", "6.145210", "6.778210"),
            ],
        },
    },
    "ED": {
        "Oredo": {
            "Ring Road / GRA": [
                ("ED/12/01/001", "King's Square (Ring Road)", "Benin City Centre", "6.334910", "5.622110"),
                ("ED/12/01/002", "Airport Road / Adesuwa Junction", "GRA, Benin City", "6.318210", "5.614210"),
            ],
        },
    },
    "DE": {
        "Warri South": {
            "Effurun / Enerhen": [
                ("DE/24/01/001", "Enerhen Junction Open Space", "Enerhen Road, Warri", "5.544210", "5.768110"),
                ("DE/24/01/002", "PTI Junction Square", "Effurun, Warri", "5.568110", "5.792110"),
            ],
        },
        "Oshimili South": {
            "Asaba Central": [
                ("DE/16/01/001", "Koka Junction Open Space", "Benin-Asaba Expressway", "6.201210", "6.712110"),
            ],
        },
    },
    "KW": {
        "Ilorin West": {
            "Ubandawaki": [
                ("23/08/11/001", "Ojude Ubandawaki", "Ubandawaki, Ilorin West", "8.493200", "4.504800"),
                ("23/08/11/003", "Govt Girls' Day Sec Sch Pakata", "Pakata Road, Ubandawaki", "8.499500", "4.519200"),
                ("23/08/11/006", "Barakat L.G.E.A Sch", "Barakat, Ubandawaki", "8.487500", "4.494500"),
            ],
            "Adewole": [
                ("23/08/01/001", "Adewole Estate Open Space", "Adewole Housing Estate, Ilorin West", "8.479200", "4.516800"),
            ],
            "Baboko": [
                ("23/08/04/001", "Baboko L.G.E.A Primary School", "Baboko / Oja Tuntun Axis, Ilorin West", "8.487700", "4.538000"),
            ],
            "Alanamu": [
                ("23/08/03/001", "Balogun Alanamu Central Open Space", "Alanamu, Ilorin West", "8.497800", "4.544600"),
            ],
            "Oko-Erin": [
                ("23/08/09/001", "Oko-Erin L.G.E.A School", "Oko-Erin, Ilorin West", "8.474800", "4.531500"),
            ],
        },
    },
}

# Representative capitals/hubs for all remaining states so every single one of Nigeria's 37 states
# has valid selectable LGAs, Wards, and Polling Units out of the box.
DEFAULT_STATE_HUBS: dict[str, tuple[str, str, str, str]] = {
    "AB": ("Aba South", "Ariaria / Eziukwu", "5.112800", "7.366700"),
    "AD": ("Yola North", "Jimeta Central", "9.279500", "12.458100"),
    "AK": ("Uyo", "Ewet Housing / Oron Road", "5.037700", "7.912800"),
    "BA": ("Bauchi", "Wunti / Central Market", "10.315800", "9.844200"),
    "BY": ("Yenagoa", "Kpansia / Swali", "4.926700", "6.267600"),
    "BE": ("Makurdi", "High Level / Wurukum", "7.733700", "8.521400"),
    "BO": ("Maiduguri", "Monday Market / GRA", "11.831100", "13.151000"),
    "CR": ("Calabar Municipal", "Marian / Watt Market", "4.975700", "8.341700"),
    "EB": ("Abakaliki", "Kpirikpiri / Presco", "6.324900", "8.113700"),
    "EK": ("Ado-Ekiti", "Oja Oba / Fajuyi", "7.621100", "5.221500"),
    "GO": ("Gombe", "Tudun Wada / Pantami", "10.289700", "11.167300"),
    "IM": ("Owerri Municipal", "Wetheral / Ikenegbu", "5.483600", "7.033300"),
    "JI": ("Dutse", "Takur / Central Market", "11.756200", "9.338900"),
    "KT": ("Katsina", "Kofar Kwaya / GRA", "12.990800", "7.601800"),
    "KB": ("Birnin Kebbi", "Badariya / Central", "12.453900", "4.197500"),
    "KG": ("Lokoja", "Ganaja / Adankolo", "7.802300", "6.733300"),
    "NA": ("Lafia", "Shabu / Modern Market", "8.491700", "8.516700"),
    "NI": ("Chanchaga", "Tunga / Bosso", "9.615200", "6.547800"),
    "ON": ("Akure South", "Alagbaka / Oba Adesida", "7.257100", "5.205800"),
    "OS": ("Osogbo", "Oke-Fia / Olaiya", "7.782700", "4.541800"),
    "PL": ("Jos North", "Terminus / Rayfield", "9.896500", "8.858300"),
    "SO": ("Sokoto North", "Kofar Atiku / Central", "13.062200", "5.233900"),
    "TA": ("Jalingo", "Mayo Gwoi / Roadblock", "8.893200", "11.359600"),
    "YO": ("Damaturu", "Nayinawa / Central", "11.747000", "11.960800"),
    "ZA": ("Gusau", "Tudun Wada / Sabon Gari", "12.162800", "6.674500"),
}


@transaction.atomic
def seed_nigeria_locations() -> dict[str, int]:
    """Idempotently seed all 37 Nigerian states, all 774 LGAs, plus Electoral Wards and Polling Units."""
    state_count = 0
    lga_count = 0
    ward_count = 0
    pu_count = 0

    states_by_code: dict[str, NigerianState] = {}
    for name, code, zone in ALL_NIGERIAN_STATES:
        state, created = NigerianState.objects.get_or_create(
            code=code,
            defaults={"name": name, "geopolitical_zone": zone},
        )
        states_by_code[code] = state
        if created:
            state_count += 1

    # Seed all 774 Nigerian LGAs across all 37 states cleanly in bulk
    existing_lga_keys = set(
        NigerianLGA.objects.values_list("state_id", "name")
    )
    new_lgas: list[NigerianLGA] = []
    for state_code, lga_names in NIGERIA_ALL_774_LGAS.items():
        state = states_by_code[state_code]
        for idx, lga_name in enumerate(lga_names, start=1):
            if (state.id, lga_name) not in existing_lga_keys:
                new_lgas.append(
                    NigerianLGA(
                        state=state,
                        name=lga_name,
                        code=f"{state_code}-{idx:02d}",
                    )
                )
    if new_lgas:
        NigerianLGA.objects.bulk_create(new_lgas, ignore_conflicts=True)
        lga_count = len(new_lgas)

    # Seed detailed wards & polling units
    for state_code, lgas_map in DETAILED_LOCATIONS.items():
        state = states_by_code[state_code]
        for lga_idx, (lga_name, wards_map) in enumerate(lgas_map.items(), start=1):
            lga, lga_created = NigerianLGA.objects.get_or_create(
                state=state,
                name=lga_name,
                defaults={"code": f"{state_code}-{lga_idx:02d}"},
            )
            if lga_created:
                lga_count += 1
            for ward_idx, (ward_name, pus) in enumerate(wards_map.items(), start=1):
                ward, ward_created = NigerianWard.objects.get_or_create(
                    lga=lga,
                    name=ward_name,
                    defaults={
                        "code": f"{ward_idx:02d}",
                        "data_source": NigerianWard.DataSource.SEED,
                    },
                )
                if ward_created:
                    ward_count += 1
                for pu_code, pu_name, landmark, lat, lon in pus:
                    pu_source = (
                        PollingUnit.DataSource.INEC
                        if pu_code[:2].isdigit()
                        else PollingUnit.DataSource.SEED
                    )
                    _, pu_created = PollingUnit.objects.get_or_create(
                        pu_code=pu_code,
                        defaults={
                            "ward": ward,
                            "name": pu_name,
                            "landmark": landmark,
                            "latitude": Decimal(lat),
                            "longitude": Decimal(lon),
                            "data_source": pu_source,
                        },
                    )
                    if pu_created:
                        pu_count += 1

    # Ensure every remaining Nigerian state hub has Wards and Polling Units out of the box
    for state_code, (lga_name, ward_name, lat, lon) in DEFAULT_STATE_HUBS.items():
        state = states_by_code[state_code]
        lga, lga_created = NigerianLGA.objects.get_or_create(
            state=state,
            name=lga_name,
            defaults={"code": f"{state_code}-01"},
        )
        if lga_created:
            lga_count += 1
        ward, ward_created = NigerianWard.objects.get_or_create(
            lga=lga,
            name=ward_name,
            defaults={"code": "01", "data_source": NigerianWard.DataSource.SEED},
        )
        if ward_created:
            ward_count += 1
        for idx, suffix in enumerate(["Main Market Open Space", "Town Hall / Primary School"], start=1):
            pu_code = f"{state_code}/01/01/{idx:03d}"
            _, pu_created = PollingUnit.objects.get_or_create(
                pu_code=pu_code,
                defaults={
                    "ward": ward,
                    "name": f"{ward_name.split('/')[0].strip()} {suffix}",
                    "landmark": f"{lga_name}, {state.name}",
                    "latitude": Decimal(lat),
                    "longitude": Decimal(lon),
                    "data_source": PollingUnit.DataSource.SEED,
                },
            )
            if pu_created:
                pu_count += 1

    return {
        "states_created": state_count,
        "lgas_created": lga_count,
        "wards_created": ward_count,
        "polling_units_created": pu_count,
        "total_states": NigerianState.objects.count(),
        "total_lgas": NigerianLGA.objects.count(),
        "total_wards": NigerianWard.objects.count(),
        "total_polling_units": PollingUnit.objects.count(),
    }


@transaction.atomic
def import_locations_from_json(json_path: str | Path) -> dict[str, int]:
    """
    Import a bulk INEC-format JSON file of states/LGAs/wards/polling units.
    Expected structure:
    [
      {
        "state": "Lagos", "state_code": "LA", "zone": "South West",
        "lga": "Ikeja", "ward": "Anifowoshe", "pu_code": "LA/11/01/001",
        "pu_name": "Open Space...", "landmark": "...", "latitude": 6.6, "longitude": 3.35
      }
    ]
    """
    raw = json.loads(Path(json_path).read_text(encoding="utf-8"))
    created_pus = 0
    for row in raw:
        state, _ = NigerianState.objects.get_or_create(
            code=row["state_code"].strip().upper(),
            defaults={
                "name": row["state"].strip(),
                "geopolitical_zone": row.get("zone", "").strip(),
            },
        )
        lga, _ = NigerianLGA.objects.get_or_create(
            state=state,
            name=row["lga"].strip(),
        )
        ward, _ = NigerianWard.objects.get_or_create(
            lga=lga,
            name=row["ward"].strip(),
        )
        lat = Decimal(str(row["latitude"])) if row.get("latitude") not in (None, "") else None
        lon = Decimal(str(row["longitude"])) if row.get("longitude") not in (None, "") else None
        _, created = PollingUnit.objects.get_or_create(
            pu_code=row["pu_code"].strip(),
            defaults={
                "ward": ward,
                "name": row["pu_name"].strip(),
                "landmark": row.get("landmark", "").strip(),
                "latitude": lat,
                "longitude": lon,
            },
        )
        if created:
            created_pus += 1
    return {"polling_units_imported": created_pus}
