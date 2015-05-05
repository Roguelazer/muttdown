import sys
import email.iterators


email.iterators._structure(email.message_from_file(sys.stdin))
