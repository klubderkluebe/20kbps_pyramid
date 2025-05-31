# 20kbps_pyramid

[20kbps](https://20kbps.net/index2.htm) is a netlabel that was founded in 2002 by Mathias Aeschlimann ([Gert 3000](https://www.discogs.com/artist/801529-Gert-3000), [haz](https://www.discogs.com/artist/318522-H%C3%A4z?anv=Haz&filter_anv=1) etc.). The original implementation evolved from static HTML to a PHP-based site that used
a filesystem-as-a-database approach and was a bit cumbersome to maintain.

In 2020, health issues forced Gert 3000 to stop maintaining 20kbps, and I stepped in to become the netlabel's owner. After publishing a few releases
the legacy way, I decided that a rewrite was due. The intention wasn't only to make it more comfortable for myself to publish new releases. The effort was undertaken also with a view to facilitating a future handover. When the day comes when I have to resign from being a netlabel head myself, and pass the torch to the next owner, they should be able to operate 20kbps with ease, and if need be, make changes to the code.

Given those requirements, the aim wasn't to create an architectonic marvel, or to make use of the technologies
*du jour*. The implementation may be a bit rustic, but the code is quite legible, I believe, and care was taken to comment and document everything in such a way that someone who is not I should be able to find their way around. Also, the new implementation has been live since [20k373](https://20kbps.net/Releases/20y20k/), and I found that the admin interface made publishing new releases a lot easier.

I made it a point to make the underlying change of engine completely transparent to the visitor. Everything looks exactly the way it did before, and [visual testing](viztest/visualTests.spec.js) was used to verify that the pages rendered are near pixel perfect replicas of the legacy pages, save for a few known exceptions.

## Docs

[Resources and credentials](RESOURCES.md) ― an inventory of the resources and credentials used in maintaining 20kbps

[Deployment](DEPLOY.md) ― deployment instructions, should it ever become necessary to re-deploy *20kbps_pyramid*. No build/deploy automation, as this is a once in a lifetime job.

[Backups](BACKUPS.md) ― description of what automated backups exist

## Code Pointers

These are good entry points for getting an overview of the code.

- [ReleaseService](pyramidprj/release_service.py#L91) ― probably the core of the admin part of *20kbps_pyramid*
- [Models](pyramidprj/models/models.py)

## Video

Watch a video showing how a release is published: [publishing_a_release.mp4](https://storage.googleapis.com/20kbps-static/assets/publishing_a_release.mp4)
