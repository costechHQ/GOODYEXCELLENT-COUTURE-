"""Background email sending (TS-04, FR-35, FR-58, NFR-15).

The enquiry is committed to the database first; the email is sent afterwards as a
background task, so a mail failure never loses the enquiry.
"""
