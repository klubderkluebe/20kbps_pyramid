def includeme(config):
    config.add_static_view("static", "static", cache_max_age=3600)
    config.add_route("home", "/")
    config.add_route("index2", "/index2.htm")
    config.add_route("Releases", "/Releases/{rlsdir}/")
    config.add_route("Releases_with_subdir", "/Releases/{rlsdir}/{subdir}/")

    config.add_route("post_something", "/post_something/")
