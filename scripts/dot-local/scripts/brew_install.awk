#!/usr/bin awk -f

function logging(msg) {
    if (dry_run) {
        print "[DRY_RUN]: " msg > "/dev/stderr"
    } else {
        print msg > "/dev/stderr"
    }
}

BEGIN {
    tmpfile = "/tmp/temp.brew_install"
    cmd_count = 0
    dry_run = (dry_run == 0) ? 0 : 1
    pick = (pick == 0 || !length(pick)) ? -1 : pick
}

/brew install/ && !/history/ && !/rff/ {
    # Remove the command number/timestamp and clean up leading space
    $1=""
    $1=$1
    gsub(/^ +/,"")

    # Handle the "--cask" flag if it's at the end
    swap=$(NF-1)
    last=$NF
    if (last == "--cask") {
        $(NF-1)=last
        $NF=swap
    }

    if (pick != -1 && $0 !~ pick) {
        next
    }

    logging("found line: " $0)

    print $0 > tmpfile

    cmd_count++
}

END {
    close(tmpfile)

    if (cmd_count > 0) {
        # Use system sort and uniq to process the commands
        cmd = "sort " tmpfile " | uniq"

        # Process the sorted and unique commands
        while ((cmd | getline sorted_cmd) > 0) {
            # Get the last field to use as filename
            n = split(sorted_cmd, fields)
            outputFile = fields[n] ".sh"

            logging("writing install-script: " outputFile)

            # Write command to its own shell script
            if (!dry_run) {
                print "#!/usr/bin/env bash\n\n" sorted_cmd > outputFile
                close(outputFile)
            }

        }

    close(cmd)

    # Clean  up temporary file
    system("rm " tmpfile)
   }
}
