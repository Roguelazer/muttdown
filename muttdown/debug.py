import email.iterators
import sys

email.iterators._structure(email.message_from_file(sys.stdin))
