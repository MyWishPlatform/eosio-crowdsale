ARGUMENT_LIST=(
	"issuer"
	"symbol"
	"decimals"
	"whitelist"
	"transferable"
	"rate"
	"ratedenom"
	"mincontrib"
	"maxcontrib"
	"softcap"
	"hardcap"
	"start"
	"finish"
	"mintdest"
	"mintval"
)

mintdests=()
mintvals=()
whitelist=true      # whitelist on
transferable=false  # transferable off
rate=150            # rate 1.5
ratedenom=100
mincontrib=1000     # min contrib 0.1 EOS
maxcontrib=100000   # max contrib 10 EOS

opts=$(getopt \
	--longoptions "$(printf "%s:," "${ARGUMENT_LIST[@]}")" \
	--name "$(basename "$0")" \
	--options "" \
	-- "$@"
)

function out() {
	mintcnt=${#mintdests[@]}
	if [[ $mintcnt != ${#mintvals[@]} ]]; then
		>&2 echo "lengths mismatch"
		return
	fi

	echo "#define ISSUER $issuer"
	echo "#define SYMBOL $symbol"
	echo "#define DECIMALS $decimals"

	echo "#define WHITELIST $whitelist"

	echo "#define TRANSFERABLE $transferable"

	echo "#define RATE $rate"
	echo "#define RATE_DENOM $ratedenom"

	echo "#define MIN_CONTRIB $mincontrib"
	echo "#define MAX_CONTRIB $maxcontrib"

	echo "#define SOFT_CAP_TKN $softcap"
	echo "#define HARD_CAP_TKN $hardcap"

	echo "#define START_DATE $start"
	echo "#define FINISH_DATE $finish"

	echo "#define MINTCNT $mintcnt"
	for i in $(seq 0 $((mintcnt - 1))); do
		echo "#define MINTDEST$i ${mintdests[$i]}"
		echo "#define MINTVAL$i ${mintvals[$i]}"
	done
}

eval set --$opts
while [[ $# -gt 0 ]]; do
	case "$1" in
		--issuer)
			issuer=$2
			shift 2
			;;

		--symbol)
			symbol=$2
			shift 2
			;;

		--decimals)
			decimals=$2
			shift 2
			;;

		--whitelist)
			whitelist=$2
			shift 2
			;;

		--transferable)
			transferable=$2
			shift 2
			;;

		--rate)
			rate=$2
			shift 2
			;;

		--ratedenom)
			ratedenom=$2
			shift 2
			;;

		--mincontrib)
			mincontrib=$2
			shift 2
			;;

		--maxcontrib)
			maxcontrib=$2
			shift 2
			;;

		--softcap)
			softcap=$2
			shift 2
			;;

		--hardcap)
			hardcap=$2
			shift 2
			;;

		--start)
			start=$2
			shift 2
			;;

		--finish)
			finish=$2
			shift 2
			;;

		--mintdest)
			mintdests+=($2)
			shift 2
			;;

		--mintval)
			mintvals+=($2)
			shift 2
			;;

		*)
			break
			;;
	esac
done

out
