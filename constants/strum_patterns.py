strum_options = [
        'Custom',
        'Down/Up',
        'Downs',
        'Ups',
        'Boom Chicka',
        'Brown Eyed Girl',
        'Somewhere Over The Rainbow',
        'Losing My Religion',
        'Skinny Love',
        'WWV',
        'WWC',
        'WWB'
]

strum_patterns = {
        'Custom': [], # should save state as user inputs their own strums

        # universal patterns (2/4, 3/4, 4/4):
        'Down/Up': ['d', 'u'],
        'Downs': ['d', ''],
        'Ups': ['', 'u'],

        # 4/4 patterns:
        'Boom Chicka': ['d', '', 'd', 'u'],
        'Brown Eyed Girl': ['d', '', 'd', 'u', '', 'u', 'd', 'u'],
        'Somewhere Over The Rainbow': ['d', '', 'd', 'u', '', 'u', 'd', ''],
        'Losing My Religion': ['d', '', 'd', '', 'd', 'u', 'd', 'u', '', 'u', 'd', '', 'd', 'u', 'd', 'u'],
        'Skinny Love': ['d', '', 'd', '', '', 'u', 'd', 'u'],

        # wonderwall strum patterns below (built for 4/4, 4 bars, double time) ->
        'WWV': ['d', '', 'd', '', 'd', '', '', 'u', 'd', 'u', 'd', '', 'd', '', '', 'u',
                'd', 'u', 'd', '', 'd', '', 'd', 'u', '', 'u', 'd', 'u', 'd', 'u', 'd', 'u', ],
        'WWC': ['d', '', 'd', '', 'd', '', '', 'u', 'd', 'u', 'd', '', 'd', '', '', 'u',
                'd', 'u', 'd', '', 'd', '', '', 'u', 'd', 'u', 'd', '', 'd', '', '', 'u'],
        'WWB': ['d', '', 'd', '', 'd', 'u', 'd', 'u', '', 'u', 'd', 'u', 'd', '', 'd', '',
                'd', 'u', 'd', '', 'd', '', 'd', 'u', '', 'u', 'd', 'u', 'd', 'u', 'd', 'u', ]
}