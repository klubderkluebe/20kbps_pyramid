def includeme(config):
    config.add_static_view("static", "static", cache_max_age=3600)
    config.add_route("home", "/")
    config.add_route("index2", "/index2.htm")
    config.add_route("Releases", "/Releases/{rlsdir}/")
    config.add_route("Releases_with_subdir", "/Releases/{rlsdir}/{subdir}/")

    config.add_route("create_release", "/create_release/")
    config.add_route("request_preview", "/request_preview/")
    config.add_route("preview_release", "/preview_release/{file}/")
    config.add_route("request_upload", "/request_upload/")
    config.add_route("check_upload", "/check_upload/{file}/")
    config.add_route("commit_release", "/commit_release/")
