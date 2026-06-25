from presidio_analyzer import (
    Pattern,
    PatternRecognizer
)

# ---------------------------------
# Aadhaar
# ---------------------------------

class AadhaarRecognizer(
    PatternRecognizer
):

    PATTERNS = [
        Pattern(
            "aadhaar",
            r"\b\d{4}\s?\d{4}\s?\d{4}\b",
            0.99
        )
    ]

    def __init__(self):

        super().__init__(
            supported_entity="AADHAAR",
            patterns=self.PATTERNS
        )


# ---------------------------------
# PAN
# ---------------------------------

class PANRecognizer(
    PatternRecognizer
):

    PATTERNS = [
        Pattern(
            "pan",
            r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
            1.0
        )
    ]

    def __init__(self):

        super().__init__(
            supported_entity="PAN",
            patterns=self.PATTERNS
        )


# ---------------------------------
# Passport
# ---------------------------------

class PassportRecognizer(
    PatternRecognizer
):

    PATTERNS = [
        Pattern(
            "passport",
            r"\b[A-Z][0-9]{7}\b",
            0.90
        )
    ]

    def __init__(self):

        super().__init__(
            supported_entity="PASSPORT",
            patterns=self.PATTERNS
        )


# ---------------------------------
# IFSC
# ---------------------------------

class IFSCRecognizer(
    PatternRecognizer
):

    PATTERNS = [
        Pattern(
            "ifsc",
            r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
            0.90
        )
    ]

    def __init__(self):

        super().__init__(
            supported_entity="IFSC",
            patterns=self.PATTERNS
        )


# ---------------------------------
# Indian Phone
# ---------------------------------

class IndianPhoneRecognizer(
    PatternRecognizer
):

    PATTERNS = [
        Pattern(
            "phone",
            r"(?<!\d)(?:\+?91[\s\-]?)?[6-9]\d{4}[\s\-]?\d{5}(?!\d)",
            0.95
        )
    ]

    def __init__(self):

        super().__init__(
            supported_entity="PHONE_NUMBER",
            patterns=self.PATTERNS
        )


# ---------------------------------
# Bank Account
# ---------------------------------

class BankAccountRecognizer(
    PatternRecognizer
):

    PATTERNS = [
        Pattern(
            "bank_account",
            r"\b(?![6-9]\d{9}\b)\d{9,18}\b",
            0.95
        )
    ]

    def __init__(self):

        super().__init__(
            supported_entity="BANK_ACCOUNT",
            patterns=self.PATTERNS
        )


# ---------------------------------
# Employee ID
# ---------------------------------

class EmployeeIDRecognizer(
    PatternRecognizer
):

    PATTERNS = [
        Pattern(
            "employee_id",
            r"\b[A-Z]{2,5}[-/]?[0-9]{3,10}\b",
            0.96
        )
    ]

    def __init__(self):

        super().__init__(
            supported_entity="EMPLOYEE_ID",
            patterns=self.PATTERNS
        )
