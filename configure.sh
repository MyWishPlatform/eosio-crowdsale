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
	"mint"
)

mintdests=()
mintvals=()

opts=$(getopt \
	--longoptions "$(printf "%s:," "${ARGUMENT_LIST[@]}")" \
	--name "$(basename "$0")" \
	--options "" \
	-- "$@"
)

function check_input() {
	for field in ${ARGUMENT_LIST[@]}; do
		if [[ $field == "mint" ]]; then
			continue
		fi
		if [[ -z "${!field}" ]]; then
			>&2 echo "missing --$field"
			err=1
		fi
	done
	if [[ -n "$err" ]]; then
		exit 0
	fi
}

function out() {
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

	mintcnt=${#mintdests[@]}
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

		--mint)
			arr=($2)
			if [[ ${#arr[@]} != 2 ]]; then
				echo "--mint arguments should be like this: \"destination value\""
				exit 0
			fi
			mintdests+=(${arr[0]})
			mintvals+=(${arr[1]})
			shift 2
			;;

		*)
			break
			;;
	esac
done

check_input
out
