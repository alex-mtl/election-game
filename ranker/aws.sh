# AWS CLI in Docker with the aws-for-claude credentials; this folder is mounted at /aws. Usage: ./aws.sh <args>
MSYS_NO_PATHCONV=1 exec docker run --rm -i -v C:/projects/claude/aws-for-claude/.aws:/root/.aws -v "$(pwd -W)":/aws amazon/aws-cli:2.37.11 "$@"
