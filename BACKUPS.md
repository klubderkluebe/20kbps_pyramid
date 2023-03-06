# 20kbps_pyramid

## Backups

*user* refers to the non-root user on the Compute Engine instance.

### Postgres database

There's a daily backup of the postgres database to a cloud storage bucket. Dumps are sent to `gs://20kbps-static-backup/00PGDUMP/`. Because they are very small, no automated deletion of old dumps is in place.

The backup is done by way of a cron job which was created as described below.

#### Cron job setup

Enable `gcloud` to use the same service account credentials which are used by the app. (Substitute *user* for `<user>`.)
```shell
gcloud auth activate-service-account --key-file=/home/<user>/20kbps_pyramid/secrets/gcloud_service_account.json
```

Create `~/.local/bin/backup_20kbps.sh with this content:
```shell
#!/usr/bin/bash
FILE=/tmp/pyramidprj/20kbps-`date +%Y-%m-%d`.pg.sql
PGPASSWORD=postgres pg_dump -U postgres -h localhost pyramidprj >$FILE
bzip2 $FILE
gsutil cp $FILE.bz2 gs://20kbps-static-backup/00PGDUMP/
rm $FILE.bz2
```

Make it executable:
```shell
chmod +x ~/.local/bin/backup_20kbps.sh
```

Edit *user*'s crontab:
```shell
crontab -e
```

Add this entry to the crontab:
```
33 9 * * * /home/<user>/.local/bin/backup_20kbps.sh >/dev/null 2>&1
```

### Backup of static asset bucket

Static assets are kept in the publicly accessible bucket `gs://20kbps-static`. The content of this bucket is copied to `gs://20kbps-static-backup` every four weeks by way of a transfer job (`20kbps-static-backup`, same name as the bucket). This means that, at any given time, there is *one* older state of `20kbps-static` which has been preserved. When the content of `20kbps-static` is corrupted, and the transfer job runs, the backup is corrupted as well. So the purpose of this backup is merely to have one 'undo' when a mistake affecting the content of `20kbps-static` is made.

