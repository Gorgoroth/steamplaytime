def webapp_add_wsgi_middleware(app):
	appstats_CALC_RPC_COSTS = True
	from google.appengine.ext.appstats import recording
	app = recording.appstats_wsgi_middleware(app)
	return app