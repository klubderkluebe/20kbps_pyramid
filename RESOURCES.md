# 20kbps_pyramid

Resources and credentials are named in terms of what is needed in order to fulfil the role of 20kbps netlabel admin. This consists mainly of publishing releases on 20kbps and posting them in various places, but includes the prerequisites for deploying the app and applying code changes.

## Resources

### GCP (Google Cloud Platform)

The netlabel runs on a *Compute Engine* instance in the project with ID *kbps-20*. (The name of the project is *20kbps*, and the ID of the project is *kbps-20*.)

With a few exceptions (which are in the app's *static* directory), static assets are in a storage bucket named *20kbps-static* in the same project as the instance. Most importantly, releases (i.e. release directories with individual files, as well as zip archives) are stored here. This bucket is publicly accessible. Files are served directly from it.

There's another bucket named *20kbps-static-backup*, the use of which is described in the [backups doc](BACKUPS.md).

### Github

The 20kbps app code repo is https://github.com/klubderkluebe/20kbps_pyramid/.

The legacy 20kbps repo is https://github.com/klubderkluebe/20kbps. This repo contains the original implementation of the netlabel, which was static HTML in the beginning, and eventually introduced PHP-rendered release pages. It includes all static files (incl. releases) that were served up to and including 20k373 (*20y20k*). The static assets in *20kbps-static* were uploaded from this repo, and the repo is also used for bootstrapping the current app's database, as described in the [deploy doc](DEPLOY.md).

### Domain

The netlabel's domain is *20kbps.net*. It is registered throuh internetbs.net.

### Email

The netlabel's email address is [contact@20kbps.net](mailto:contact@20kbps.net).

### Archive.org

The netlabel's archive.org account is https://archive.org/details/@20_kbps_rec.

### Discogs

The netlabel's Discogs account is https://www.discogs.com/user/20kbps.

### Socials

- Twitter: https://twitter.com/20kbps
- Mastodon: https://mastodon.online/@20kbps


## Credentials


### GCP

- Owner-level access to project *kbps-20*
    - by having the password and TOTP key for account `jonas.santoso@gmail.com`
    - or by being given this access level
- Credentials for service account `programmatic-release-managemen@kbps-20.iam.gserviceaccount.com`
    - The app uses a JSON credentials file for this account to access the *20kbps-static* bucket.

### Github

In order to clone the repos on the instance, the Github user used on the instance must have at least read access to the repos. Currently this is realized through Github user `kbps-20-pyramid`, so the password for this account would be part of a handover.

In order to apply code changes to the `20kbps_pyramid` repo, write access to this repo must be granted. This can be done by Github organization `klubderkluebe`, of which `santosoj` is owner.
  - It is, of course, entirely possible to hard-fork the repo, given read access, and deploy the fork as the live netlabel site.

### Domain

In order to manage DNS for the website as well as for email, the admin needs to have access to the netlabel's account with the registrar. Currently this is account `jonas.santoso@protonmail.com` on [internet.bs](https://internet.bs).

### Email

The netlabel's email address, [contact@20kbps.net](mailto:contact@20kbps.net) is currently hosted on [Zoho Mail](https://www.zoho.com/mail/).
  - A handover would include the account password for [contact@20kbps.net](mailto:contact@20kbps.net) on Zoho Mail.
  - Given access to the netlabel's DNS records, a different email provider can be set up for the *20kbps.net* domain.

### Archive.org

- The username for the netlabel's archive.org account is *contact@20kbps.net*. A handover would include the password for this account.
- The archive.org S3 credentials which the app uses for uploading releases to archive.org were obtained by logging into the account and going to https://archive.org/account/s3.php.

### Discogs.com

- The username for the netlabel's Discogs account is *contact@20kbps.net*. A handover would include the password for this account.

### Socials

- Password for Twitter account `@20kbps`
- Password for Mastodon account `@20kbps@mastodon.online`