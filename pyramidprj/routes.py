def includeme(config):
    config.add_static_view("static", "static", cache_max_age=3600)
    config.add_route("home", "/")
    config.add_route("index2", "/index2.htm")
    config.add_route("Releases", "/Releases/{rlsdir}/")
    config.add_route("Releases_with_subdir", "/Releases/{rlsdir}/{subdir}/")

    config.add_route("create_release", "/create_release/")
    config.add_route("post_new_release_file", "/post_new_release_file/")
    config.add_route("confirm_new_release", "/confirm_new_release/")
