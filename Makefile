
FLASK_APP=gotchufam.app


.PHONY: run
run: venv
	. venv/bin/activate ; \
	  FLASK_APP=$(FLASK_APP) FLASK_DEBUG=1 flask run -h 0.0.0.0 --extra-files gotchufam/static:gotchufam/templates

run-peer-server:
	node_modules/.bin/peerjs --port 9000 --key peerjs --path /gotchufam-peering


venv: requirements.txt
	rm -rf venv || true
	python3 -m virtualenv -p python3 venv.tmp
	. venv.tmp/bin/activate && \
	  pip3 install -r requirements.txt && \
	  (sed -i '/VIRTUAL_ENV\|^#!/s/venv/venv/' `find venv.tmp -type f -exec grep -Iq . {} \; -print` || true) && \
	  mv venv.tmp venv


.PHONY: initialize
initialize: init-config init-db


.PHONY: init-config
init-config:
	if [ -f instance/gotchufam.ini ] ; then \
	  mv instance/gotchufam.ini instance/gotchufam.ini.bak; \
	fi
	if ! [ -d instance ] ; then mkdir instance ; fi
	. venv/bin/activate ; \
	GOTCHUFAM_UNCONFIGURED=1 FLASK_APP=$(FLASK_APP) FLASK_DEBUG=1 flask init-config instance/gotchufam.ini


.PHONY: init-db
init-db:
	if [ -f instance/app.db ] ; then \
	  mv instance/app.db instance/app.db.bak; \
	fi
	if ! [ -d instance ] ; then mkdir instance ; fi
	. venv/bin/activate ; \
	FLASK_APP=$(FLASK_APP) FLASK_DEBUG=1 flask init-db


.PHONY: precommit
precommit: venv
	. venv/bin/activate; \
	  black .

