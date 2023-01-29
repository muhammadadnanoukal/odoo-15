# Part of Odoo. See LICENSE file for full copyright and licensing details.

SUPPORTED_BRANDS = (
    'VISA',
    'MASTER',
    'AMEX',
)

# ISO 4217 codes of currencies supported by hyperpay
SUPPORTED_CURRENCIES = (
    'AED',
    'SAR',
    'AUD',
    'BRL',
    'CAD',
    'CNY',
    'CZK',
    'DKK',
    'EUR',
    'HKD',
    'HUF',
    'ILS',
    'JPY',
    'MYR',
    'MXN',
    'TWD',
    'NZD',
    'NOK',
    'PHP',
    'PLN',
    'GBP',
    'RUB',
    'SGD',
    'SEK',
    'CHF',
    'THB',
    'USD',
)

PAYMENT_STATUS_MAPPING = {
    'pending': (
        '^(000\.200)', # Result codes for pending transactions
        '^(800\.400\.5|100\.400\.500)' , # these codes describe a situation where the status of a transaction can change even after several days
    ),
    'done': (
        '^(000\.000\.|000\.100\.1|000\.[36])', # Result codes for successfully processed transactions
        '^(000\.400\.0[^3]|000\.400\.[0-1]{2}0)'  # Result codes for successfully processed transactions that should be manually reviewed
    ),
    'cancel': (
        '^(000\.400\.[1][0-9][1-9]|000\.400\.2)', # Result codes for rejections due to 3Dsecure and Intercard risk checks
        '^(800\.[17]00|800\.800\.[123])' , # Result codes for rejections by the external bank or similar payment system
        '^(900\.[1234]00|000\.400\.030)',  # Result codes for rejections due to communication errors
        '^(800\.[56]|999\.|600\.1|800\.800\.[84])', # Result codes for rejections due to system errors
        '^(100\.39[765])', # Result codes for rejections due to error in asynchonous workflow
        '^(300\.100\.100)', # Result codes for Soft Declines
        '^(100\.400\.[0-3]|100\.38|100\.370\.100|100\.370\.11)', # Result codes for rejections due to checks by external risk systems
        '^(800\.400\.1)', # Result codes for rejections due to address validation
        '^(800\.400\.2|100\.380\.4|100\.390)', # Result codes for rejections due to 3Dsecure
        '^(100\.100\.701|800\.[32])', # Result codes for rejections due to blacklist validation
        '^(800\.1[123456]0)' , # Result codes for rejections due to risk validation
        '^(600\.[23]|500\.[12]|800\.121)', # Result codes for rejections due to configuration validation
        '^(100\.[13]50)', # Result codes for rejections due to registration validation
        '^(100\.250|100\.360)', # Result codes for rejections due to job validation
        '^(700\.[1345][05]0)', # Result codes for rejections due to reference validation
        '^(200\.[123]|100\.[53][07]|800\.900|100\.[69]00\.500)', # Result codes for rejections due to format validation
        '^(100\.800)', # Result codes for rejections due to address validation
        '^(100\.[97]00)', # Result codes for rejections due to contact validation
        '^(100\.100|100.2[01])', # Result codes for rejections due to account validation
        '^(100\.55)', # Result codes for rejections due to amount validation
        '^(100\.380\.[23]|100\.380\.101)', # Result codes for rejections due to risk management
        '^(000\.100\.2)', # Chargeback related result codes

    ),
}
