PolishTrainsGTFS
================

> ⚠️🏗️ This project is still under construction. The static generator works,
> although it produces a low-quality feed. The realtime generator has not been tested,
> even if it works, most likely it generates invalid trip_id and stop_sequence references.

Creates a single, GTFS and GTFS-Realtime feeds for all Polish trains coordinated by [PKP PLK](https://www.plk-sa.pl/)
(this excludes [WKD](https://wkd.com.pl/) or [UBB](https://www.ubb-online.com/)), including:

- [PolRegio](https://polregio.pl/)
- [PKP Intercity](https://www.intercity.pl/)
- [Koleje Mazowieckie](https://mazowieckie.com.pl/pl)
- [PKP SKM w Trójmieście](https://www.skm.pkp.pl/)
- [Koleje Śląskie](https://www.kolejeslaskie.pl/)
- [Koleje Dolnośląskie](https://kolejedolnoslaskie.pl/)
- [Koleje Wielkopolskie](https://koleje-wielkopolskie.com.pl/)
- [SKM Warszawa](https://www.skm.warszawa.pl/)
- [Łódzka Kolej Aglomeracyjna](https://lka.lodzkie.pl/)
- [Koleje Małopolskie](https://kolejemalopolskie.com.pl/)
- [Arriva RP](https://arriva.pl/)
- [RegioJet](https://regiojet.pl/)
- [Leo Express](https://www.leoexpress.com/pl)


Data comes from the [Otwarte Dane Kolejowe API from PKP PLK](https://pdp-api.plk-sa.pl/).


Running
-------

PolishTrainsGTFS is written in Python with the [Impuls framework](https://github.com/MKuranowski/Impuls).

To set up the project, run:

```terminal
$ python -m venv .venv
$ . .venv/bin/activate
$ pip install -Ur requirements.txt
```

Then, run:

```terminal
$ export PKP_PLK_APIKEY=paste_your_apikey_here
$ python -m polish_trains_gtfs.static
```

The resulting schedules will be put in a file called `polish_trains.zip`.

See `python -m polish_trains_gtfs.static --help` for a list of all available options.

To create the GTFS-Realtime feed, run `python -m polish_trains_gtfs.realtime`.


API Keys
--------

In order to run this script, an apikey for [Otwarte Dane Kolejowe](https://pdp-api.plk-sa.pl/)
is required. It must be provided in the `PKP_PLK_APIKEY` environment variable. For development,
use your IDE .env file support to avoid having to `export` it in your shell.

PolishTrainsGTFS also supports Docker-style secret passing. Instead of setting the apikey
directly, a path to a file containing the apikey may be provided in the `PKP_PLK_APIKEY_FILE`
environment variable. Note that `PKP_PLK_APIKEY` takes precedence if both variables are set.


License
-------

_PolishTrainsGTFS_ is provided under the MIT license, included in the `LICENSE` file.
