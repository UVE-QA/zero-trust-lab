# ---------------------------------------------------------------------------
# Remote state.
#
# The account already holds a Terraform state bucket, versioned and encrypted,
# carrying several projects under prefixes. This stack joins it under its own
# prefix rather than standing up a second one.
#
# That is not only less machinery -- it also removes the bootstrap loop
# entirely. A stack that creates the bucket holding its own state must be
# applied once with local state and then migrated, and the error it produces
# on a fresh clone looks like a typo. None of that arises here.
#
# The bucket name embeds the account id, so it is not committed. Initialise
# with a backend config file that stays out of git:
#
#     cp backend.hcl.example backend.hcl     # then fill in
#     terraform init -backend-config=backend.hcl
#
# Locking uses the S3 lock file rather than a DynamoDB table: the account has
# no lock table, and a table exists to be paid for and maintained.
# ---------------------------------------------------------------------------

terraform {
  backend "s3" {
    # All values supplied by -backend-config=backend.hcl
  }
}
