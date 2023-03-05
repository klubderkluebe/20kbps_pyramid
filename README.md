# 20kbps_pyramid

## Deployment

*user* refers to the non-root user on the Compute Engine instance.

### Create Compute Engine instance

Get a *Compute Engine* instance on GCP. (*e2-medium* at the time of writing.) Create it in *europe-north1-a*, because that's where the storage bucket is.

#### SSH

- Locally, create an SSH key *first*, so it can be added to the instance at creation.

#### Some settings

**Boot disk**:
  - 20 GB
  - Ubuntu 22.04 LTS

**Identity and API access**:
  - Service account: *Programmatic Release Management* (programmatic-release-managemen@kbps-20.iam.gserviceaccount.com)

**Firewall**
  - Allow HTTP traffic
  - Allow HTTPS traffic

**Advanced options / Security**
  - Disable vTPM / Integrity Monitoring
  - Under *VM access* / *Add manually generated SSH keys*, add the SSH key that was created for this instance locally.

#### SSH / Verify login

- Verify sshing into instance is successful.
    - Create an entry in ~/.ssh/config, use the correct *IdentityFile*, and specify the same *User* that is used on the instance.

### Install pyenv and Python on the instance

Remove the Apache2 package that's installed by default and upgrade the instance:
```shell
sudo su
apt remove apache2
apt update
apt dist-upgrade
```

Install some packages to enable features when building Python from pyenv:
```shell
apt install -y build-essential gdb lcov pkg-config \
    libbz2-dev libffi-dev libgdbm-dev libgdbm-compat-dev liblzma-dev \
    libncurses5-dev libreadline6-dev libsqlite3-dev libssl-dev \
    lzma lzma-dev tk-dev uuid-dev zlib1g-dev
```

As *user*, install `pyenv`:
```shell
curl https://pyenv.run | bash
```

Add the following to *user*'s `.bashrc`:
```shell
export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
```
Then install and select Python 3.10.4. (`install` takes some time because Python is built.)
```shell
source ~/.bashrc
pyenv install 3.10.4
pyenv global 3.10.4
```

### Clone into repo and install requirements

On the instance, create an SSH key:
```shell
ssh-keygen
```
Github user [*kbps-20-pyramid*](https://github.com/kbps-20-pyramid) has been given *Read* access to repo [*klubderkluebe/20kbps_pyramid*](https://github.com/klubderkluebe/20kbps_pyramid). The SSH key just generated needs to be added to Github user *kbps-20-pyramid*'s SSH keys.

In *user*'s home directory, clone into *20kbps_pyramid*:
```shell
git clone git@github.com:klubderkluebe/20kbps_pyramid.git
```

Install postgres. (Required by `psycopg2` during Python package setup.)
```shell
apt install postgres-all
```

Inside the *20kbps_pyramid* directory, run setup. Make sure this is done using the 3.10.4 Python from pyenv.
```shell
python setup.py install
```
    "googleapis-common-protos==1.57.1",

Due to a stupid bug, it is necessary to apply this fix:
```shell
pip uninstall -y protobuf googleapis-common-protos google-api-core google-cloud-core google-cloud-storage
pip install google==3.0.0 google-auth==2.15.0 google-cloud==0.34.0 protobuf==4.21.12 \
    googleapis-common-protos==1.57.1 google-api-core==2.11.0 google-cloud-core==2.3.2 \
    google-cloud-storage==2.7.0
cd ~/.pyenv/versions/3.10.4/lib/python3.10/site-packages/google
touch __init__.py
```
Without this, the following error would be encountered later:
```
ModuleNotFoundError: No module named 'google.protobuf'
```

### Set up temp directory and secrets

Create a writable temp directory. 
```shell
mkdir /tmp/pyramidprj && chmod a+rw /tmp/pyramidprj
```

Inside *20kbps_pyramid*, create the *secrets* directory:
```shell
mkdir secrets
```

Copy the secrets into *secrets*. The following files should be there:
  - *archive_org_s3.json*
      - *archive.org* S3 bucket access key and secret for user *20kbps* specified in this format:
        ```json
        {
          "s3": {
              "access": "<ACCESS KEY>",
              "secret": "<SECRET>"
          }
        }
        ```
  - *basic_auth.json*
      - HTTP Basic Auth username/password for the admin interface. Set this to anything desired and specify as:
        ```json
        {
            "username": "<USERNAME>",
            "password": "<PASSWORD>"
        }        
        ```
  - *gcloud_service_account.json*
      - Service account credentials for account programmatic-release-managemen@kbps-20.iam.gserviceaccount.com.


### Bootstrap database

Set password for user *postgres* to *postgres*. As root:
```shell
passwd postgres
```
Switch user to *postgres* and start `psql`:
```shell
su postgres
psql
```

In *psql*, set password for user *postgres* to *postgres* as well. (This is okay because postgres accepts only local connections by default.)
```
\password postgres
```

In *user*'s home directory, clone into *20kbps* in order to have legacy files available for bootstrapping. Github user *kbps-20-pyramid* has been given *Read* access to this repo as well.
```shell
git clone git@github.com:klubderkluebe/20kbps.git
```

Even though the packages are installed by *setup.py*, it is necessary to issue the *pip* command again in order to create the shims. (Make sure the versions match the ones that are already installed.)
```shell
pip install alembic==1.9.1 pyramid==2.0
```

Install PHP8. (Required by the `php-whisperer` package for parsing some PHP code.)
```shell
apt install php8.1
```

Inside *20kbps_pyramid*, run the bootstrap script:
```shell
./bootstrap_db.sh
```

When run successfully, it parses legacy content from the filesystem, and initializes a postgres database named `pyramidprj` with all release data up to and including 20k373 (*20y20k*). The bootstrap script drops the database and does this from scratch every time it is run.
